import json
import re
import xml.etree.ElementTree as ET


JUNIT_PATH = "test-results.xml"
BRUNO_PATH = "bruno-results.json"


# --------------------------------------------------
# Load Bruno JSON
#
# Build:
# CUTECH-xxxx -> failed/error assertion details
# --------------------------------------------------

with open(BRUNO_PATH, "r", encoding="utf-8") as f:
    bruno_data = json.load(f)


assertion_failures = {}


for iteration in bruno_data:
    for result in iteration.get("results", []):

        name = result.get("name", "")

        match = re.search(
            r"\b(CUTECH-\d+)\b",
            name
        )

        if not match:
            continue

        test_key = match.group(1)

        assertions = (
            result.get("assertionResults")
            or []
        )

        # Treat both assertion failures and assertion errors
        # as failed regression results.
        failed = [
            assertion
            for assertion in assertions
            if assertion.get("status") in ("fail", "error")
        ]

        assertion_failures[test_key] = failed


# --------------------------------------------------
# Load JUnit
# --------------------------------------------------

tree = ET.parse(JUNIT_PATH)
root = tree.getroot()

kept = 0
removed = 0


# --------------------------------------------------
# Process each JUnit testsuite
# --------------------------------------------------

for testsuite in list(root.findall("testsuite")):

    for testcase in list(
        testsuite.findall("testcase")
    ):

        name = testcase.get("name", "")

        match = re.search(
            r"\b(CUTECH-\d+)\b",
            name
        )

        # --------------------------------------------------
        # Remove Bruno declarative assertion JUnit rows.
        #
        # Only the Jira/Xray mapping testcase should remain
        # for each Bruno request.
        # --------------------------------------------------

        if not match:
            testsuite.remove(testcase)
            removed += 1
            continue

        test_key = match.group(1)


        # --------------------------------------------------
        # Add Xray test_key property
        # --------------------------------------------------

        properties = testcase.find(
            "properties"
        )

        if properties is None:
            properties = ET.Element(
                "properties"
            )

            testcase.insert(
                0,
                properties
            )


        existing_property = properties.find(
            "./property[@name='test_key']"
        )

        if existing_property is None:

            property_element = ET.SubElement(
                properties,
                "property"
            )

            property_element.set(
                "name",
                "test_key"
            )

            property_element.set(
                "value",
                test_key
            )

        else:

            existing_property.set(
                "value",
                test_key
            )


        # --------------------------------------------------
        # Remove any existing Bruno mapping-test status.
        #
        # runtime.assertions / bruno-results.json are the
        # source of truth for regression PASS/FAIL.
        # --------------------------------------------------

        existing_failure = testcase.find(
            "failure"
        )

        if existing_failure is not None:
            testcase.remove(
                existing_failure
            )


        existing_error = testcase.find(
            "error"
        )

        if existing_error is not None:
            testcase.remove(
                existing_error
            )


        # --------------------------------------------------
        # Apply result from THIS request's declarative
        # assertions.
        # --------------------------------------------------

        failed_assertions = (
            assertion_failures.get(
                test_key,
                []
            )
        )


        if failed_assertions:

            descriptions = []


            for assertion in failed_assertions:

                lhs = (
                    assertion.get("lhs")
                    or assertion.get("lhsExpr")
                    or assertion.get("expression")
                    or "Assertion"
                )


                # Preserve falsey expected values such as
                # 0, False and "".
                rhs = None

                for field in (
                    "rhs",
                    "rhsExpr",
                    "expected"
                ):
                    if (
                        field in assertion
                        and assertion[field] is not None
                    ):
                        rhs = assertion[field]
                        break


                description = lhs


                if rhs is not None:
                    description += (
                        " " + str(rhs)
                    )


                error = assertion.get(
                    "error"
                )


                if isinstance(
                    error,
                    dict
                ):
                    error_message = (
                        error.get("message")
                    )

                elif isinstance(
                    error,
                    str
                ):
                    error_message = error

                else:
                    error_message = None


                if error_message:
                    description += (
                        ": " + error_message
                    )


                descriptions.append(
                    description
                )


            # --------------------------------------------------
            # Mark the Jira/Xray mapping testcase as FAILED
            # --------------------------------------------------

            failure = ET.SubElement(
                testcase,
                "failure"
            )

            failure.set(
                "message",
                (
                    f"{len(failed_assertions)} "
                    "declarative assertion(s) failed"
                )
            )

            failure.text = "\n".join(
                descriptions
            )


            print(
                f"FAILED {test_key}: "
                f"{len(failed_assertions)} "
                "assertion(s)"
            )


        else:

            print(
                f"PASSED {test_key}: "
                "all declarative assertions passed"
            )


        print(
            f"Mapped {name} -> {test_key}"
        )

        kept += 1


    # --------------------------------------------------
    # Recalculate testsuite counts after removing the
    # Bruno assertion-generated JUnit rows.
    # --------------------------------------------------

    remaining = list(
        testsuite.findall("testcase")
    )


    # Remove empty suites.
    if not remaining:
        root.remove(testsuite)
        continue


    failures = sum(
        1
        for testcase in remaining
        if testcase.find("failure")
        is not None
    )


    errors = sum(
        1
        for testcase in remaining
        if testcase.find("error")
        is not None
    )


    skipped = sum(
        1
        for testcase in remaining
        if testcase.find("skipped")
        is not None
    )


    testsuite.set(
        "tests",
        str(len(remaining))
    )

    testsuite.set(
        "failures",
        str(failures)
    )

    testsuite.set(
        "errors",
        str(errors)
    )

    testsuite.set(
        "skipped",
        str(skipped)
    )


# --------------------------------------------------
# Basic validation
# --------------------------------------------------

if kept == 0:
    raise SystemExit(
        "ERROR: No Jira/Xray testcase "
        "keys were found in JUnit"
    )


# --------------------------------------------------
# Validate every remaining testcase has a valid
# Xray test_key.
# --------------------------------------------------

test_keys = []


for testsuite in root.findall("testsuite"):

    for testcase in testsuite.findall(
        "testcase"
    ):

        testcase_name = testcase.get(
            "name",
            "UNKNOWN"
        )


        properties = testcase.find(
            "properties"
        )


        if properties is None:
            raise SystemExit(
                f"ERROR: Testcase "
                f"'{testcase_name}' "
                "has no properties element"
            )


        test_key_property = properties.find(
            "./property[@name='test_key']"
        )


        if test_key_property is None:
            raise SystemExit(
                f"ERROR: Testcase "
                f"'{testcase_name}' "
                "has no Xray test_key"
            )


        test_key = test_key_property.get(
            "value"
        )


        if not test_key:
            raise SystemExit(
                f"ERROR: Testcase "
                f"'{testcase_name}' "
                "has an empty Xray test_key"
            )


        if not re.fullmatch(
            r"CUTECH-\d+",
            test_key
        ):
            raise SystemExit(
                f"ERROR: Invalid Xray "
                f"test_key '{test_key}'"
            )


        test_keys.append(
            test_key
        )


# --------------------------------------------------
# Detect duplicate Jira/Xray test keys.
#
# Two Bruno requests must never map to the same
# Xray Test issue.
# --------------------------------------------------

duplicates = sorted(
    {
        key
        for key in test_keys
        if test_keys.count(key) > 1
    }
)


if duplicates:
    raise SystemExit(
        "ERROR: Duplicate Xray test keys "
        f"detected: {', '.join(duplicates)}"
    )


# --------------------------------------------------
# Validation summary
# --------------------------------------------------

print("")
print(
    f"Validated Xray testcases: "
    f"{len(test_keys)}"
)

print(
    "All Xray test_key mappings "
    "are valid and unique."
)


# --------------------------------------------------
# Write dynamic testcase count for GitHub Actions
# --------------------------------------------------

with open(
    "xray-testcase-count.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(str(len(test_keys)))


print(
    f"Expected Xray testcase count: "
    f"{len(test_keys)}"
)


# --------------------------------------------------
# Write transformed JUnit
# --------------------------------------------------

tree.write(
    JUNIT_PATH,
    encoding="utf-8",
    xml_declaration=True
)


# --------------------------------------------------
# Final summary
# --------------------------------------------------

print("")
print(
    f"Xray testcases kept: {kept}"
)

print(
    "Bruno assertion testcases removed: "
    f"{removed}"
)
