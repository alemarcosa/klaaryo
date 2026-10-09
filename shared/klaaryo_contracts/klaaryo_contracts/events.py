"""Canonical event definitions for the Klaaryo platform."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


CANDIDATE_CREATED = "candidate.created"
CANDIDATE_UPDATED = "candidate.updated"
CANDIDATE_TOPICS = [CANDIDATE_CREATED, CANDIDATE_UPDATED]


class InvalidEvent(Exception):
    """Raised when an event payload is missing required fields."""


@dataclass(frozen=True)
class CandidateEvent:
    event_id: str
    event_type: str
    occurred_at: str
    candidate_pk: int
    ats_source: str
    external_id: str
    changed_fields: list[str] = field(default_factory=list)

    @classmethod
    def new(
        cls,
        event_type: str,
        candidate_pk: int,
        ats_source: str,
        external_id: str,
        changed_fields: list[str],
    ) -> CandidateEvent:
        return cls(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            occurred_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            candidate_pk=candidate_pk,
            ats_source=ats_source,
            external_id=external_id,
            changed_fields=changed_fields,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> CandidateEvent:
        required = {
            "event_id", "event_type", "occurred_at",
            "candidate_pk", "ats_source", "external_id",
        }
        missing = required - set(d)
        if missing:
            raise InvalidEvent(f"Missing fields: {sorted(missing)}")
        return cls(
            event_id=d["event_id"],
            event_type=d["event_type"],
            occurred_at=d["occurred_at"],
            candidate_pk=d["candidate_pk"],
            ats_source=d["ats_source"],
            external_id=d["external_id"],
            changed_fields=d.get("changed_fields", []),
        )
