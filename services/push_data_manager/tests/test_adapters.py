"""T2: Parametrized adapter normalization tests."""
import os
import pytest
from datetime import date, datetime, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from push_data_manager.adapters.schema import (
    NormalizedCandidate,
    NormalizationError,
    RawApplication,
    SkipReason,
    InternalStatus,
)
from push_data_manager.adapters.ats.alpha import AlphaAdapter
from push_data_manager.adapters.ats.beta import BetaAdapter
from push_data_manager.utils.dates import age_at


# --- Alpha tests ---

class TestAlphaNormalize:
    adapter = AlphaAdapter(base_url="http://fake", timeout=5)

    def _raw(self, overrides: dict | None = None) -> RawApplication:
        base = {
            "id": "alpha-1001",
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario@example.com",
            "phone_number": "+39 333 1234567",
            "birth_date": "1995-06-15",
            "application_status": "NEW",
            "job_id": "JOB-001",
            "applied_at": "2026-10-01T12:00:00Z",
        }
        if overrides:
            base.update(overrides)
        return RawApplication(
            external_id=base["id"],
            watermark=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            payload=base,
        )

    def test_valid_mapping(self):
        c = self.adapter.normalize(self._raw())
        assert c.external_id == "alpha-1001"
        assert c.ats_source == "alpha"
        assert c.first_name == "Mario"
        assert c.last_name == "Rossi"
        assert c.email == "mario@example.com"
        assert c.phone == "+393331234567"
        assert c.internal_status == InternalStatus.NEW
        assert c.job_external_id == "JOB-001"
        assert c.age == age_at(date(1995, 6, 15), date(2026, 10, 1))

    def test_unknown_status(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"application_status": "ON_HOLD"}))
        assert exc.value.reason == SkipReason.UNKNOWN_STATUS

    def test_missing_birth_date(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"birth_date": ""}))
        assert exc.value.reason == SkipReason.MISSING_BIRTH_DATE

    def test_invalid_birth_date(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"birth_date": "1995-13-45"}))
        assert exc.value.reason == SkipReason.INVALID_BIRTH_DATE

    @pytest.mark.parametrize("status_in,status_out", [
        ("NEW", InternalStatus.NEW),
        ("IN_REVIEW", InternalStatus.IN_REVIEW),
        ("REJECTED", InternalStatus.REJECTED),
        ("HIRED", InternalStatus.HIRED),
    ])
    def test_all_statuses(self, status_in, status_out):
        c = self.adapter.normalize(self._raw({"application_status": status_in}))
        assert c.internal_status == status_out


# --- Beta tests ---

class TestBetaNormalize:
    adapter = BetaAdapter(base_url="http://fake", timeout=5)

    def _raw(self, overrides: dict | None = None) -> RawApplication:
        base = {
            "candidate_uuid": "beta-xxxx-xxxx-0001",
            "full_name": "Alessandro Neri",
            "contact": {
                "email_address": "alessandro@example.com",
                "mobile": "+39 340 1111111",
            },
            "age": 29,
            "stage": "new_application",
            "job_reference": "JOB-B-001",
            "submitted_timestamp": 1728388800,
        }
        if overrides:
            for k, v in overrides.items():
                if "." in k:
                    parts = k.split(".", 1)
                    base.setdefault(parts[0], {})
                    base[parts[0]][parts[1]] = v
                else:
                    base[k] = v
        return RawApplication(
            external_id=base["candidate_uuid"],
            watermark=datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc),
            payload=base,
        )

    def test_valid_mapping(self):
        c = self.adapter.normalize(self._raw())
        assert c.external_id == "beta-xxxx-xxxx-0001"
        assert c.ats_source == "beta"
        assert c.first_name == "Alessandro"
        assert c.last_name == "Neri"
        assert c.email == "alessandro@example.com"
        assert c.phone == "+393401111111"
        assert c.age == 29
        assert c.internal_status == InternalStatus.NEW

    def test_name_split_multi_word(self):
        c = self.adapter.normalize(self._raw({"full_name": "Maria Grazia Rossi"}))
        assert c.first_name == "Maria"
        assert c.last_name == "Grazia Rossi"

    def test_missing_age(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"age": None}))
        assert exc.value.reason == SkipReason.MISSING_AGE

    def test_invalid_age(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"age": "ventotto"}))
        assert exc.value.reason == SkipReason.INVALID_AGE

    def test_unknown_stage(self):
        with pytest.raises(NormalizationError) as exc:
            self.adapter.normalize(self._raw({"stage": "interview_scheduled"}))
        assert exc.value.reason == SkipReason.UNKNOWN_STATUS

    def test_missing_contact(self):
        raw = self._raw()
        raw.payload["contact"] = None
        c = self.adapter.normalize(raw)
        assert c.email == ""
        assert c.phone == ""

    @pytest.mark.parametrize("stage_in,status_out", [
        ("new_application", InternalStatus.NEW),
        ("screening", InternalStatus.IN_REVIEW),
        ("not_a_fit", InternalStatus.REJECTED),
        ("offer_accepted", InternalStatus.HIRED),
    ])
    def test_all_stages(self, stage_in, status_out):
        c = self.adapter.normalize(self._raw({"stage": stage_in}))
        assert c.internal_status == status_out


# --- age_at boundary tests ---

class TestAgeAt:
    def test_birthday_on_applied_date(self):
        """Turns 18 on the day of application -> age 18."""
        assert age_at(date(2008, 10, 1), date(2026, 10, 1)) == 18

    def test_birthday_day_before(self):
        """Turns 18 the day after application -> age 17."""
        assert age_at(date(2008, 10, 2), date(2026, 10, 1)) == 17
