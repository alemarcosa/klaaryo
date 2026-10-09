"""Business validation rules for normalized candidates.

These rules are common to all ATS sources and apply in the order below.
Only the first failing reason is recorded.
"""
from __future__ import annotations

from push_data_manager.adapters.schema import NormalizedCandidate, NormalizationError, SkipReason
from push_data_manager.utils.contact import is_valid_email


def validate(c: NormalizedCandidate) -> None:
    """Validate a normalized candidate. Raises NormalizationError on first failure."""
    # 1. Name
    if not c.first_name and not c.last_name:
        raise NormalizationError(SkipReason.MISSING_NAME, "first_name and last_name are both empty")

    # 2. Email
    if not c.email:
        raise NormalizationError(SkipReason.MISSING_EMAIL, "email is empty")
    if not is_valid_email(c.email):
        raise NormalizationError(SkipReason.INVALID_EMAIL, f"invalid email: {c.email}")

    # 3. Phone
    if not c.phone:
        raise NormalizationError(SkipReason.MISSING_PHONE, "phone is empty")

    # 4. Underage
    if c.age < 18:
        raise NormalizationError(SkipReason.UNDERAGE, f"age={c.age}")
