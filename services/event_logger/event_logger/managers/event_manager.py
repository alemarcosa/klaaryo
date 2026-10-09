"""Event manager: record events with dedup via unique constraint."""
from __future__ import annotations

import json
from enum import StrEnum

from django.db import IntegrityError, transaction

from klaaryo_contracts.events import CandidateEvent, InvalidEvent
from event_logger.db_models.models import ProcessedEvent


class RecordResult(StrEnum):
    PROCESSED = "processed"
    DUPLICATE = "duplicate"


class EventManager:
    def record(self, payload: dict) -> RecordResult:
        """Record an event. Returns PROCESSED or DUPLICATE.

        No check-then-insert: the unique constraint on event_id
        is the single source of truth for dedup.
        """
        event = CandidateEvent.from_dict(payload)

        try:
            with transaction.atomic():
                ProcessedEvent.objects.create(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    candidate_pk=event.candidate_pk,
                    ats_source=event.ats_source,
                    payload_json=json.dumps(payload),
                )
            return RecordResult.PROCESSED
        except IntegrityError:
            return RecordResult.DUPLICATE

    def list_events(
        self,
        event_type: str = "",
        ats_source: str = "",
    ) -> list[dict]:
        qs = ProcessedEvent.objects.all()
        if event_type:
            qs = qs.filter(event_type=event_type)
        if ats_source:
            qs = qs.filter(ats_source=ats_source)
        return [
            json.loads(e.payload_json)
            for e in qs
        ]
