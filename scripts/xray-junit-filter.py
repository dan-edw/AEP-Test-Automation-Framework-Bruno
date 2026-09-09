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
#
# Also collect the expected Jira/Xray test keys
# independently from Bruno JSON.
# --------------------------------------------------

with open(BRUNO_PATH, "r", encoding="utf-8") as f:
    bruno_data = json.load(f)


assertion_failures = {}
expected_test_keys = []


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

        expected_test_keys.append(
            test_key
        )

        assertions = (
            result.get("assertionResults")
            or []
        )

        failed = [
            assertion
            for assertion in assertions
            if assertion.get("status") in ("fail", "error")
        ]

        assertion_failures[test_key] = failed


# --------------------------------------------------
# Validate Bruno JSON mappings before touching JUnit
# --------------------------------------------------

if not expected_test_keys:
    raise SystemExit(
        "ERROR: No Jira/Xray test keys "
        "were found in bruno-results.json"
    )


expected_duplicates = sorted(
    {
        key
        for key in expected_test_keys
        if expected_test_keys.count(key) > 1
    }
)


if expected_duplicates:
    raise SystemExit(
        "ERROR: Duplicate Jira/Xray keys "
        "found in Bruno results: "
        f"{', '.join(expected_duplicates)}"
    )


expected_test_keys = sorted(
    set(expected_test_keys)
)


expected_count = len(
    expected_test_keys
)


print("")
print(
    f"Expected Jira/Xray tests from Bruno JSON: "
    f"{expected_count}"
)

print(
    "Expected Jira/Xray keys: "
    f"{', '.join(expected_test_keys)}"
)


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

        name = testcase.get(
            "name",
            ""
        )

        match = re.search(
            r"\b(CUTECH-\d+)\b",
            name
        )

        # --------------------------------------------------
        # Remove Bruno declarative assertion JUnit rows.
        #
        # Only Jira/Xray mapping testcases remain.
        # --------------------------------------------------

        if not match:
            testsuite.remove(
                testcase
            )

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
        # Remove existing mapping test failure/error.
        #
        # Declarative assertions are the source of truth.
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
        # Apply status from THIS request's declarative
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


                # Preserve falsey values:
                # 0, False, ""
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
    # Recalculate testsuite counts
    # --------------------------------------------------

    remaining = list(
        testsuite.findall("testcase")
    )


    if not remaining:
        root.remove(
            testsuite
        )
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
# Validate final Xray-ready JUnit
# --------------------------------------------------

if kept == 0:
    raise SystemExit(
        "ERROR: No Jira/Xray testcase "
        "keys were found in JUnit"
    )


actual_test_keys = []


for testsuite in root.findall(
    "testsuite"
):

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


        actual_test_keys.append(
            test_key
        )


# --------------------------------------------------
# Detect duplicate keys in final JUnit
# --------------------------------------------------

actual_duplicates = sorted(
    {
        key
        for key in actual_test_keys
        if actual_test_keys.count(key) > 1
    }
)


if actual_duplicates:
    raise SystemExit(
        "ERROR: Duplicate Xray test keys "
        "in filtered JUnit: "
        f"{', '.join(actual_duplicates)}"
    )


actual_test_keys = sorted(
    set(actual_test_keys)
)


actual_count = len(
    actual_test_keys
)


# --------------------------------------------------
# Compare Bruno JSON against filtered JUnit
# --------------------------------------------------

missing_from_junit = sorted(
    set(expected_test_keys)
    - set(actual_test_keys)
)


unexpected_in_junit = sorted(
    set(actual_test_keys)
    - set(expected_test_keys)
)


if missing_from_junit:
    raise SystemExit(
        "ERROR: Jira/Xray tests were present "
        "in Bruno JSON but missing from "
        "filtered JUnit: "
        f"{', '.join(missing_from_junit)}"
    )


if unexpected_in_junit:
    raise SystemExit(
        "ERROR: Filtered JUnit contains "
        "unexpected Jira/Xray tests: "
        f"{', '.join(unexpected_in_junit)}"
    )


if actual_count != expected_count:
    raise SystemExit(
        "ERROR: Jira/Xray testcase count "
        f"mismatch. Expected {expected_count}, "
        f"found {actual_count}"
    )


# --------------------------------------------------
# Validation summary
# --------------------------------------------------

print("")
print(
    f"Expected Xray testcases: "
    f"{expected_count}"
)

print(
    f"Filtered Xray testcases: "
    f"{actual_count}"
)

print(
    "All Xray test_key mappings "
    "are valid, unique and complete."
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
    f"Xray testcases kept: "
    f"{kept}"
)

print(
    "Bruno assertion testcases removed: "
    f"{removed}"
)
