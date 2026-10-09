"""Modify a field in the ATS Alpha data file.

Usage: python tools/set_field.py <id> <field> <value>
Example: python tools/set_field.py alpha-1004 application_status HIRED
"""
import json
import sys
from pathlib import Path

DATA_PATH = Path("/data/applications.json")


def main() -> None:
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <id> <field> <value>", file=sys.stderr)
        sys.exit(1)

    record_id, field, value = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(DATA_PATH) as f:
        records = json.load(f)

    found = False
    for r in records:
        if r["id"] == record_id:
            old_value = r.get(field)
            r[field] = value
            found = True
            print(f"Updated {record_id}.{field}: {old_value!r} -> {value!r}")
            break

    if not found:
        print(f"Record {record_id} not found", file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, "w") as f:
        json.dump(records, f, indent=2)


if __name__ == "__main__":
    main()
