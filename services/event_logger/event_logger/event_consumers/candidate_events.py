"""Consumer for candidate events from the event bus."""
from __future__ import annotations

import logging

from klaaryo_contracts.events import CANDIDATE_TOPICS, InvalidEvent
from event_logger.managers.event_manager import EventManager, RecordResult

logger = logging.getLogger(__name__)


class CandidateEventsConsumer:
    def __init__(self, subscriber, manager: EventManager) -> None:
        self._subscriber = subscriber
        self._manager = manager

    def run(self) -> None:
        self._subscriber.run(CANDIDATE_TOPICS, self._handle)

    def _handle(self, topic: str, payload: dict) -> None:
        try:
            result = self._manager.record(payload)
        except InvalidEvent as e:
            logger.error("[ERROR] malformed event: %s payload=%s", e, payload)
            return  # ack the poison message

        event_id = payload.get("event_id", "?")
        event_type = payload.get("event_type", "?")

        if result == RecordResult.PROCESSED:
            print(f"[PROCESSED] event_id={event_id} type={event_type}")
        else:
            print(f"[SKIPPED] event_id={event_id} duplicate")
