import json
import re
import xml.etree.ElementTree as ET


JUNIT_PATH = "test-results.xml"
BRUNO_PATH = "bruno-results.json"


# --------------------------------------------------
# Load Bruno JSON
# Build:
# CUTECH-xxxx -> failed assertion details
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

        failed = [
            assertion
            for assertion in assertions
            if assertion.get("status") == "fail"
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

        # Remove Bruno declarative assertion rows.
        # Only Jira/Xray mapping testcases remain.
        if not match:
            testsuite.remove(testcase)
            removed += 1
            continue

        test_key = match.group(1)

        # ------------------------------------------
        # Add Xray test_key property
        # ------------------------------------------

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

        # ------------------------------------------
        # Remove any existing mapping-test failure
        # ------------------------------------------

        existing_failure = testcase.find(
            "failure"
        )

        if existing_failure is not None:
            testcase.remove(
                existing_failure
            )

        # ------------------------------------------
        # Apply result from this request's
        # declarative assertions
        # ------------------------------------------

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

                rhs = (
                    assertion.get("rhs")
                    or assertion.get("rhsExpr")
                    or assertion.get("expected")
                )

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


    # ----------------------------------------------
    # Recalculate testsuite counts
    # ----------------------------------------------

    remaining = list(
        testsuite.findall("testcase")
    )

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
# Validation
# --------------------------------------------------

if kept == 0:
    raise SystemExit(
        "ERROR: No Jira/Xray testcase "
        "keys were found in JUnit"
    )


# --------------------------------------------------
# Write transformed JUnit
# --------------------------------------------------

tree.write(
    JUNIT_PATH,
    encoding="utf-8",
    xml_declaration=True
)


print("")
print(
    f"Xray testcases kept: {kept}"
)
print(
    "Bruno assertion testcases removed: "
    f"{removed}"
)
