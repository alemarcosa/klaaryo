"""ATS Beta adapter."""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import requests

from push_data_manager.adapters.ats.base import AtsAdapter, AtsUnavailable
from push_data_manager.adapters.schema import (
    InternalStatus,
    NormalizedCandidate,
    NormalizationError,
    RawApplication,
    SkipReason,
)
from push_data_manager.utils.contact import normalize_email, normalize_phone
from push_data_manager.utils.dates import from_unix

_STATUS_MAP: dict[str, InternalStatus] = {
    "new_application": InternalStatus.NEW,
    "screening": InternalStatus.IN_REVIEW,
    "not_a_fit": InternalStatus.REJECTED,
    "offer_accepted": InternalStatus.HIRED,
}


class BetaAdapter(AtsAdapter):
    source: ClassVar[str] = "beta"

    def fetch_since(self, since: datetime) -> list[RawApplication]:
        url = f"{self.base_url}/v2/candidates"
        since_unix = int(since.timestamp())
        params = {"updated_after": since_unix}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise AtsUnavailable(f"Beta ATS error: {e}") from e

        results = []
        for record in resp.json():
            ext_id = record.get("candidate_uuid")
            watermark = None
            updated_ts = record.get("updated_timestamp")
            if updated_ts is not None:
                watermark = from_unix(updated_ts)
            results.append(RawApplication(
                external_id=ext_id,
                watermark=watermark,
                payload=record,
            ))
        return results

    def normalize(self, raw: RawApplication) -> NormalizedCandidate:
        p = raw.payload

        ext_id = p.get("candidate_uuid")
        if not ext_id:
            raise NormalizationError(SkipReason.MISSING_EXTERNAL_ID, "candidate_uuid is empty")

        # Name splitting: lossy
        full_name = p.get("full_name", "")
        parts = full_name.split(maxsplit=1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

        # Contact
        contact = p.get("contact") or {}
        email = normalize_email(contact.get("email_address"))
        phone = normalize_phone(contact.get("mobile"))

        # Age: must be int, not bool, not None
        age_raw = p.get("age")
        if age_raw is None:
            raise NormalizationError(SkipReason.MISSING_AGE, "age is null")
        if isinstance(age_raw, bool) or not isinstance(age_raw, int):
            raise NormalizationError(
                SkipReason.INVALID_AGE,
                f"invalid age: {age_raw}",
            )
        age = age_raw

        # Status
        stage_raw = p.get("stage", "")
        status = _STATUS_MAP.get(stage_raw)
        if status is None:
            raise NormalizationError(
                SkipReason.UNKNOWN_STATUS,
                f"unknown stage: {stage_raw}",
            )

        # Submitted timestamp -> applied_at
        submitted_ts = p.get("submitted_timestamp")
        if submitted_ts is None:
            raise NormalizationError(SkipReason.INVALID_APPLIED_AT, "submitted_timestamp missing")
        applied_at = from_unix(submitted_ts)

        return NormalizedCandidate(
            external_id=ext_id,
            ats_source=self.source,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            age=age,
            job_external_id=p.get("job_reference", ""),
            internal_status=status,
            applied_at=applied_at,
        )
