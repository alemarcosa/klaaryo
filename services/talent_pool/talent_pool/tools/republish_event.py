"""Republish an event from the outbox.

Usage:
    python -m talent_pool.tools.republish_event --last
    python -m talent_pool.tools.republish_event --event-id <uuid>
"""
import argparse
import os
import sys

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from talent_pool.managers.outbox_relay import OutboxRelay


def main() -> None:
    parser = argparse.ArgumentParser(description="Republish an outbox event")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--event-id", type=str, help="UUID of the event to republish")
    group.add_argument("--last", action="store_true", help="Republish the last published event")
    args = parser.parse_args()

    try:
        OutboxRelay.mark_for_republish(
            event_id=args.event_id,
            last=args.last,
        )
        print("Event marked for republish.")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
