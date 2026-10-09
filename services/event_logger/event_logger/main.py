"""Composition root for the event_logger consumer."""
from __future__ import annotations

import logging
import os
import sys

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from klaaryo_bus import subscriber_from_env
from event_logger.event_consumers.candidate_events import CandidateEventsConsumer
from event_logger.managers.event_manager import EventManager


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    subscriber = subscriber_from_env()
    manager = EventManager()
    consumer = CandidateEventsConsumer(subscriber, manager)
    logging.getLogger(__name__).info("Starting event_logger consumer...")
    consumer.run()


if __name__ == "__main__":
    main()
