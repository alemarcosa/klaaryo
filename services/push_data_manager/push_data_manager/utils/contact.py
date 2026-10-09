"""Contact normalization utilities."""
from __future__ import annotations

import re

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str:
    """Strip and lowercase. Returns '' if None or empty."""
    if not value:
        return ""
    return value.strip().lower()


def normalize_phone(value: str | None) -> str:
    """Strip, remove spaces and hyphens. Returns '' if None."""
    if value is None:
        return ""
    return re.sub(r"[\s-]", "", value.strip())


def is_valid_email(email: str) -> bool:
    """Simple email validation."""
    return bool(_EMAIL_REGEX.match(email))
