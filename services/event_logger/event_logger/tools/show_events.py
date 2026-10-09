"""Show processed events.

Usage:
    python -m event_logger.tools.show_events [--type candidate.updated] [--source alpha]
"""
import argparse
import json
import os
import sys

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from event_logger.managers.event_manager import EventManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Show processed events")
    parser.add_argument("--type", dest="event_type", default="", help="Filter by event type")
    parser.add_argument("--source", dest="ats_source", default="", help="Filter by ATS source")
    args = parser.parse_args()

    manager = EventManager()
    events = manager.list_events(
        event_type=args.event_type,
        ats_source=args.ats_source,
    )
    for event in events:
        print(json.dumps(event))

    if not events:
        print("No events found.")


if __name__ == "__main__":
    main()
