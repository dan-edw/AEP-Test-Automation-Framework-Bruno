from pathlib import Path
from collections import defaultdict
import re
import sys

COLLECTION_PATH = Path("bruno/collections/aep-regression")

KEY_PATTERN = re.compile(r"CUTECH-\d+")
TEST_PATTERN = re.compile(
    r'\btest\s*\(\s*["\'](CUTECH-\d+)["\']'
)

errors = []
keys_to_files = defaultdict(list)
files_checked = 0

if not COLLECTION_PATH.is_dir():
    print(f"ERROR: Collection not found: {COLLECTION_PATH}")
    sys.exit(1)

for file in sorted(COLLECTION_PATH.rglob("*.request.yml")):
    files_checked += 1
    content = file.read_text(encoding="utf-8")

    filename_match = KEY_PATTERN.search(file.stem)

    if not filename_match:
        errors.append(f"{file.name}: No CUTECH key in filename")
        continue

    filename_key = filename_match.group()
    script_keys = TEST_PATTERN.findall(content)

    if len(script_keys) != 1:
        errors.append(
            f"{file.name}: Expected exactly one Jira test() key, "
            f"found {script_keys}"
        )
        continue

    script_key = script_keys[0]
    keys_to_files[script_key].append(str(file))

    if filename_key != script_key:
        errors.append(
            f"{file.name}: Filename key {filename_key} "
            f"does not match script key {script_key}"
        )

for key, files in keys_to_files.items():
    if len(files) > 1:
        errors.append(
            f"Duplicate Xray key {key} found in: "
            + ", ".join(files)
        )

if files_checked == 0:
    errors.append("No Bruno request files found")

print(f"Bruno request files checked: {files_checked}")
print(f"Unique Xray keys found: {len(keys_to_files)}")

if errors:
    print("\nBRUNO VALIDATION FAILED")
    for error in errors:
        print(f"ERROR: {error}")

    sys.exit(1)

print("\nBRUNO VALIDATION PASSED")
print("All request files have unique, matching Xray test keys.")
