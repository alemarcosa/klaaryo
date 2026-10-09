"""Modify a field in the ATS Beta data file.

Usage: python tools/set_field.py <uuid> <field> <value>
Example: python tools/set_field.py beta-xxxx-xxxx-0001 stage hired

For nested fields like contact.email_address, use dot notation:
  python tools/set_field.py beta-xxxx-xxxx-0001 contact.email_address new@email.com
"""
import json
import sys
from pathlib import Path

DATA_PATH = Path("/data/applications.json")


def main() -> None:
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <uuid> <field> <value>", file=sys.stderr)
        sys.exit(1)

    record_uuid, field, value = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(DATA_PATH) as f:
        records = json.load(f)

    found = False
    for r in records:
        if r["candidate_uuid"] == record_uuid:
            if "." in field:
                parts = field.split(".", 1)
                container = r.get(parts[0], {})
                old_value = container.get(parts[1])
                container[parts[1]] = value
                r[parts[0]] = container
            else:
                old_value = r.get(field)
                # Try to preserve type for numeric fields
                try:
                    value = int(value)
                except ValueError:
                    pass
                r[field] = value
            found = True
            print(f"Updated {record_uuid}.{field}: {old_value!r} -> {value!r}")
            break

    if not found:
        print(f"Record {record_uuid} not found", file=sys.stderr)
        sys.exit(1)

    with open(DATA_PATH, "w") as f:
        json.dump(records, f, indent=2)


if __name__ == "__main__":
    main()
