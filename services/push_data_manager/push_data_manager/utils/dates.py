"""Date and time utilities."""
from __future__ import annotations

from datetime import date, datetime, timezone


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO 8601 datetime string and ensure it's UTC-aware."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_iso_z(dt: datetime) -> str:
    """Format a datetime as ISO 8601 with Z suffix."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def from_unix(ts: int | float) -> datetime:
    """Convert a Unix timestamp to a UTC-aware datetime."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def age_at(birth: date, on_date: date) -> int:
    """Calculate age at a specific date, handling birthday correctly."""
    age = on_date.year - birth.year
    if (on_date.month, on_date.day) < (birth.month, birth.day):
        age -= 1
    return age
