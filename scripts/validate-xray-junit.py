from pathlib import Path
from collections import Counter
import re
import sys
import xml.etree.ElementTree as ET

REPORT = Path("test-results.xml")
KEY_PATTERN = re.compile(r"^CUTECH-\d+$")

errors = []

if not REPORT.is_file():
    sys.exit("ERROR: Xray JUnit file not found")

root = ET.parse(REPORT).getroot()
testcases = root.findall(".//testcase")

if not testcases:
    sys.exit("ERROR: No JUnit testcases found")

keys = []

for case in testcases:
    name = case.get("name", "")
    props = case.find("properties")

    test_keys = []
    test_ids = []

    if props is not None:
        for prop in props.findall("property"):
            if prop.get("name") == "test_key":
                test_keys.append(prop.get("value", ""))

            if prop.get("name") == "test_id":
                test_ids.append(prop.get("value", ""))

    if len(test_keys) != 1:
        errors.append(
            f"{name}: Expected exactly one test_key"
        )
        continue

    key = test_keys[0]
    keys.append(key)

    if test_ids:
        errors.append(
            f"{name}: Unexpected test_id property"
        )

    if not KEY_PATTERN.fullmatch(key):
        errors.append(f"Invalid Xray key: {key}")

    name_match = re.search(r"CUTECH-\d+", name)

    if not name_match:
        errors.append(
            f"No Jira key in testcase name: {name}"
        )
    elif name_match.group() != key:
        errors.append(
            f"Mismatch: {name} maps to {key}"
        )

for key, count in Counter(keys).items():
    if count > 1:
        errors.append(
            f"Duplicate Xray key: {key}"
        )

print(f"JUnit testcases: {len(testcases)}")
print(f"Mapped Xray keys: {len(keys)}")

if errors:
    print("\nXRAY JUNIT VALIDATION FAILED")

    for error in errors:
        print(f"ERROR: {error}")

    sys.exit(1)

print("\nXRAY JUNIT VALIDATION PASSED")
