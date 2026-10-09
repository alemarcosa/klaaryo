"""ATS Alpha adapter."""
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
from push_data_manager.utils.dates import age_at, parse_iso_utc, to_iso_z

_STATUS_MAP: dict[str, InternalStatus] = {
    "NEW": InternalStatus.NEW,
    "IN_REVIEW": InternalStatus.IN_REVIEW,
    "REJECTED": InternalStatus.REJECTED,
    "HIRED": InternalStatus.HIRED,
}


class AlphaAdapter(AtsAdapter):
    source: ClassVar[str] = "alpha"

    def fetch_since(self, since: datetime) -> list[RawApplication]:
        url = f"{self.base_url}/api/applications"
        params = {"since": to_iso_z(since)}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise AtsUnavailable(f"Alpha ATS error: {e}") from e

        results = []
        for record in resp.json():
            ext_id = record.get("id")
            watermark = None
            updated_at_raw = record.get("updated_at")
            if updated_at_raw:
                watermark = parse_iso_utc(updated_at_raw)
            results.append(RawApplication(
                external_id=ext_id,
                watermark=watermark,
                payload=record,
            ))
        return results

    def normalize(self, raw: RawApplication) -> NormalizedCandidate:
        p = raw.payload

        ext_id = p.get("id")
        if not ext_id:
            raise NormalizationError(SkipReason.MISSING_EXTERNAL_ID, "id is empty")

        # Status mapping
        status_raw = p.get("application_status", "")
        status = _STATUS_MAP.get(status_raw)
        if status is None:
            raise NormalizationError(
                SkipReason.UNKNOWN_STATUS,
                f"unknown status: {status_raw}",
            )

        # Applied at
        applied_at_raw = p.get("applied_at")
        if not applied_at_raw:
            raise NormalizationError(SkipReason.INVALID_APPLIED_AT, "applied_at missing")
        applied_at = parse_iso_utc(applied_at_raw)

        # Birth date -> age
        birth_date_raw = p.get("birth_date")
        if not birth_date_raw:
            raise NormalizationError(SkipReason.MISSING_BIRTH_DATE, "birth_date missing")
        try:
            from datetime import date
            birth_date = date.fromisoformat(birth_date_raw)
        except (ValueError, TypeError):
            raise NormalizationError(
                SkipReason.INVALID_BIRTH_DATE,
                f"invalid birth_date: {birth_date_raw}",
            )
        age = age_at(birth_date, applied_at.date())

        return NormalizedCandidate(
            external_id=ext_id,
            ats_source=self.source,
            first_name=p.get("first_name", ""),
            last_name=p.get("last_name", ""),
            email=normalize_email(p.get("email")),
            phone=normalize_phone(p.get("phone_number")),
            age=age,
            job_external_id=p.get("job_id", ""),
            internal_status=status,
            applied_at=applied_at,
        )
