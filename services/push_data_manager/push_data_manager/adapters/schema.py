"""Internal schema for normalized candidate data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class InternalStatus(StrEnum):
    NEW = "new"
    IN_REVIEW = "in_review"
    REJECTED = "rejected"
    HIRED = "hired"


class SkipReason(StrEnum):
    MISSING_EXTERNAL_ID = "missing_external_id"
    MISSING_NAME = "missing_name"
    MISSING_EMAIL = "missing_email"
    INVALID_EMAIL = "invalid_email"
    MISSING_PHONE = "missing_phone"
    MISSING_BIRTH_DATE = "missing_birth_date"
    INVALID_BIRTH_DATE = "invalid_birth_date"
    MISSING_AGE = "missing_age"
    INVALID_AGE = "invalid_age"
    UNDERAGE = "underage"
    UNKNOWN_STATUS = "unknown_status"
    INVALID_APPLIED_AT = "invalid_applied_at"
    REJECTED_BY_TALENT_POOL = "rejected_by_talent_pool"


@dataclass(frozen=True)
class NormalizedCandidate:
    external_id: str
    ats_source: str
    first_name: str
    last_name: str
    email: str
    phone: str
    age: int
    job_external_id: str
    internal_status: InternalStatus
    applied_at: datetime  # aware, UTC


@dataclass(frozen=True)
class RawApplication:
    external_id: str | None
    watermark: datetime | None
    payload: dict


class NormalizationError(Exception):
    def __init__(self, reason: SkipReason, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}")
