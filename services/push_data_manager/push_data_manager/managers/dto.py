"""Data transfer objects for the sync manager."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SyncReport:
    ats_source: str
    pulled: int
    pushed: int
    skipped: int
    skipped_reasons: dict[str, int]
    created: int
    updated: int
    unchanged: int
    since: str  # ISO string
    cursor: str  # ISO string


@dataclass(frozen=True)
class SyncStatus:
    ats_source: str
    last_sync_at: str | None  # ISO string
    total_pushed: int
    total_skipped: int
    cursor: str | None
