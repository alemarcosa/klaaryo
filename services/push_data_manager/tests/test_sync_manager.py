"""T3: Sync manager tests with fake adapter and client."""
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from push_data_manager.adapters.schema import (
    InternalStatus,
    NormalizedCandidate,
    NormalizationError,
    RawApplication,
    SkipReason,
)
from push_data_manager.adapters.ats.base import AtsAdapter, AtsUnavailable
from push_data_manager.adapters.talent_pool_client import TalentPoolClient, TalentPoolUnavailable, UpsertOutcome
from push_data_manager.managers.sync_manager import SyncManager
from push_data_manager.managers.exceptions import SyncFailed, UnknownAtsSource
from push_data_manager.db_models.models import SyncRun


NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


def _valid_candidate(ext_id: str = "test-001") -> NormalizedCandidate:
    return NormalizedCandidate(
        external_id=ext_id,
        ats_source="test",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        phone="+39333000111",
        age=30,
        job_external_id="JOB-001",
        internal_status=InternalStatus.NEW,
        applied_at=NOW - timedelta(hours=2),
    )


class FakeAdapter(AtsAdapter):
    source = "test"

    def __init__(self):
        super().__init__(base_url="http://fake", timeout=5)
        self.records: list[RawApplication] = []

    def fetch_since(self, since: datetime) -> list[RawApplication]:
        return self.records

    def normalize(self, raw: RawApplication) -> NormalizedCandidate:
        return _valid_candidate(raw.external_id or "test")


class FakeTalentPool:
    def __init__(self):
        self.calls = []

    def upsert(self, c: NormalizedCandidate) -> UpsertOutcome:
        self.calls.append(c)
        return UpsertOutcome(candidate_pk=len(self.calls), created=True, changed_fields=[])


@pytest.fixture
def fake_adapter():
    return FakeAdapter()


@pytest.fixture
def fake_tp():
    return FakeTalentPool()


def _manager(adapter, tp):
    return SyncManager(
        adapter_factory=lambda source: adapter,
        talent_pool=tp,
        clock=lambda: NOW,
    )


@pytest.mark.django_db(transaction=True)
def test_cursor_advances_to_max_watermark(fake_adapter, fake_tp):
    w1 = NOW - timedelta(hours=1)
    w2 = NOW - timedelta(minutes=30)
    fake_adapter.records = [
        RawApplication("a", w1, {}),
        RawApplication("b", w2, {}),
    ]
    mgr = _manager(fake_adapter, fake_tp)
    report = mgr.run("test")
    assert report.pushed == 2
    # Cursor should be the latest watermark
    last_run = SyncRun.objects.filter(ats_source="test", status="success").latest("finished_at")
    assert last_run.cursor == w2


@pytest.mark.django_db(transaction=True)
def test_overlap_applied_on_subsequent_sync(fake_adapter, fake_tp):
    # First sync
    w = NOW - timedelta(hours=1)
    fake_adapter.records = [RawApplication("a", w, {})]
    mgr = _manager(fake_adapter, fake_tp)
    mgr.run("test")

    # Second sync: adapter.fetch_since should be called with cursor - overlap
    call_args = []
    original_fetch = fake_adapter.fetch_since
    def tracking_fetch(since):
        call_args.append(since)
        return original_fetch(since)
    fake_adapter.fetch_since = tracking_fetch
    fake_adapter.records = [RawApplication("a", w, {})]

    mgr.run("test")
    from django.conf import settings
    expected_since = w - timedelta(seconds=settings.SYNC_CURSOR_OVERLAP_SECONDS)
    assert call_args[0] == expected_since


@pytest.mark.django_db(transaction=True)
def test_talent_pool_unavailable_cursor_unchanged(fake_adapter):
    w = NOW - timedelta(hours=1)
    fake_adapter.records = [RawApplication("a", w, {})]

    tp = MagicMock()
    tp.upsert.side_effect = TalentPoolUnavailable("connection refused")

    mgr = _manager(fake_adapter, tp)
    with pytest.raises(SyncFailed):
        mgr.run("test")

    # No success runs should exist
    assert SyncRun.objects.filter(ats_source="test", status="success").count() == 0


@pytest.mark.django_db(transaction=True)
def test_skipped_counted_by_reason(fake_adapter, fake_tp):
    fake_adapter.records = [
        RawApplication("ok", NOW, {}),
        RawApplication("bad1", NOW, {}),
        RawApplication("bad2", NOW, {}),
    ]

    call_count = [0]
    original_normalize = fake_adapter.normalize
    def counting_normalize(raw):
        call_count[0] += 1
        if raw.external_id and raw.external_id.startswith("bad"):
            raise NormalizationError(SkipReason.MISSING_EMAIL, "email empty")
        return original_normalize(raw)
    fake_adapter.normalize = counting_normalize

    mgr = _manager(fake_adapter, fake_tp)
    report = mgr.run("test")
    assert report.pulled == 3
    assert report.pushed == 1
    assert report.skipped == 2
    assert report.skipped_reasons["missing_email"] == 2
    assert report.pulled == report.pushed + report.skipped
