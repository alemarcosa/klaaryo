"""Data transfer objects for the talent_pool service."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CandidateData:
    external_id: str
    ats_source: str
    first_name: str
    last_name: str
    email: str
    phone: str
    age: int
    job_external_id: str
    internal_status: str
    applied_at: datetime


@dataclass(frozen=True)
class UpsertOutcome:
    candidate_pk: int
    created: bool
    changed_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateDTO:
    candidate_pk: int
    external_id: str
    ats_source: str
    first_name: str
    last_name: str
    email: str
    phone: str
    age: int
    job_external_id: str
    internal_status: str
    applied_at: datetime
    created_at: datetime
    updated_at: datetime
