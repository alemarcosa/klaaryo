"""Persistent store for fake ATS Beta.

Same pattern as Alpha but with Beta's field names:
- submitted_timestamp (unix int) instead of applied_at
- updated_timestamp (unix int) instead of updated_at
- Rebase only submitted_timestamp, never birth_date or age.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED_PATH = Path("/app/fixtures/applications.seed.json")
DATA_PATH = Path("/data/applications.json")


def _rebase_timestamps(records: list[dict]) -> list[dict]:
    """Shift submitted_timestamp so the most recent one is ~1 hour ago."""
    now_unix = int(time.time())
    target = now_unix - 3600  # 1 hour ago

    max_submitted = max(r["submitted_timestamp"] for r in records)
    delta = target - max_submitted

    for r in records:
        r["submitted_timestamp"] = r["submitted_timestamp"] + delta
    return records


def _record_hash(record: dict) -> str:
    """Stable hash of a record's content (excluding updated_timestamp)."""
    data = {k: v for k, v in sorted(record.items()) if k != "updated_timestamp"}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class ChangeTracker:
    """Tracks per-record hashes to detect modifications."""

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}
        self._updated_timestamps: dict[str, int] = {}

    def process(self, records: list[dict]) -> list[dict]:
        now_unix = int(time.time())
        result = []
        for r in records:
            rid = r["candidate_uuid"]
            h = _record_hash(r)
            prev = self._hashes.get(rid)
            if prev is None:
                # First load: updated_timestamp = submitted_timestamp
                updated = r.get("updated_timestamp") or r["submitted_timestamp"]
            elif prev != h:
                # Content changed since last read
                updated = now_unix
            else:
                # Unchanged: preserve previous updated_timestamp
                updated = self._updated_timestamps.get(rid, r.get("updated_timestamp") or r["submitted_timestamp"])

            self._hashes[rid] = h
            self._updated_timestamps[rid] = updated
            r["updated_timestamp"] = updated
            result.append(r)
        return result


def init_data() -> None:
    """Copy and rebase the seed fixture if /data/applications.json doesn't exist."""
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        with open(SEED_PATH) as f:
            records = json.load(f)
        records = _rebase_timestamps(records)
        with open(DATA_PATH, "w") as f:
            json.dump(records, f, indent=2)


def load_records(tracker: ChangeTracker) -> list[dict]:
    """Load records from disk and apply change tracking."""
    with open(DATA_PATH) as f:
        records = json.load(f)
    return tracker.process(records)
