"""Persistent store for fake ATS Alpha.

On first startup, copies the seed fixture to /data/applications.json
with rebased timestamps so the most recent applied_at is ~1 hour ago.
Subsequent restarts use the persisted file as-is.

A ChangeTracker detects modifications by hashing each record and
setting updated_at = now when a hash changes.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED_PATH = Path("/app/fixtures/applications.seed.json")
DATA_PATH = Path("/data/applications.json")


def _rebase_timestamps(records: list[dict]) -> list[dict]:
    """Shift applied_at so the most recent one is ~1 hour ago."""
    now = datetime.now(timezone.utc)
    target = now - timedelta(hours=1)

    max_applied = max(
        datetime.fromisoformat(r["applied_at"].replace("Z", "+00:00"))
        for r in records
    )
    delta = target - max_applied

    for r in records:
        original = datetime.fromisoformat(r["applied_at"].replace("Z", "+00:00"))
        rebased = original + delta
        r["applied_at"] = rebased.strftime("%Y-%m-%dT%H:%M:%SZ")
    return records


def _record_hash(record: dict) -> str:
    """Stable hash of a record's content (excluding updated_at)."""
    data = {k: v for k, v in sorted(record.items()) if k != "updated_at"}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class ChangeTracker:
    """Tracks per-record hashes to detect modifications.
    
    Limitations: state is in-memory; a restart resets tracking
    (but updated_at will equal applied_at for unmodified records).
    """

    def __init__(self) -> None:
        self._hashes: dict[str, str] = {}
        self._updated_at: dict[str, str] = {}

    def process(self, records: list[dict]) -> list[dict]:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        result = []
        for r in records:
            rid = r["id"]
            h = _record_hash(r)
            prev = self._hashes.get(rid)
            if prev is None:
                # First load: updated_at = applied_at
                updated = r.get("updated_at") or r["applied_at"]
            elif prev != h:
                # Content changed since last read
                updated = now_iso
            else:
                # Unchanged: preserve previous updated_at
                updated = self._updated_at.get(rid, r.get("updated_at") or r["applied_at"])

            self._hashes[rid] = h
            self._updated_at[rid] = updated
            r["updated_at"] = updated
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
