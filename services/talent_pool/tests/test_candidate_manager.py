"""T1: Core idempotency tests for CandidateManager."""
import os
import pytest
from datetime import datetime, timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("EVENT_BUS_BACKEND", "memory")

import django
django.setup()

from klaaryo_bus.in_memory import InMemoryBus
from talent_pool.managers.candidate_manager import CandidateManager
from talent_pool.managers.outbox_relay import OutboxRelay
from talent_pool.db_models.models import OutboxEvent


@pytest.fixture
def manager():
    return CandidateManager()


@pytest.fixture
def sample_data():
    from talent_pool.managers.dto import CandidateData
    return CandidateData(
        external_id="test-001",
        ats_source="alpha",
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        phone="+39333000111",
        age=30,
        job_external_id="JOB-001",
        internal_status="new",
        applied_at=datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.django_db(transaction=True)
def test_create(manager, sample_data):
    """(a) create -> created=True and 1 outbox candidate.created."""
    outcome = manager.upsert(sample_data)
    assert outcome.created is True
    assert outcome.changed_fields == []

    events = list(OutboxEvent.objects.all())
    assert len(events) == 1
    assert events[0].topic == "candidate.created"
    assert events[0].payload["event_type"] == "candidate.created"
    assert events[0].payload["changed_fields"] == []


@pytest.mark.django_db(transaction=True)
def test_idempotent_upsert(manager, sample_data):
    """(b) same payload -> created=False, changed_fields=[], 0 new outbox."""
    manager.upsert(sample_data)
    OutboxEvent.objects.all().delete()  # Clear first creation event

    outcome = manager.upsert(sample_data)
    assert outcome.created is False
    assert outcome.changed_fields == []
    assert OutboxEvent.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_update_with_changed_fields(manager, sample_data):
    """(c) change status and phone -> changed_fields=["internal_status","phone"] and 1 outbox candidate.updated."""
    from dataclasses import replace
    manager.upsert(sample_data)
    OutboxEvent.objects.all().delete()

    updated_data = replace(
        sample_data,
        internal_status="hired",
        phone="+39333999888",
    )
    outcome = manager.upsert(updated_data)
    assert outcome.created is False
    assert outcome.changed_fields == ["internal_status", "phone"]

    events = list(OutboxEvent.objects.all())
    assert len(events) == 1
    assert events[0].topic == "candidate.updated"
    assert events[0].payload["changed_fields"] == ["internal_status", "phone"]


@pytest.mark.django_db(transaction=True)
def test_outbox_relay_publishes_in_order(manager, sample_data):
    """(d) OutboxRelay.publish_pending with InMemoryBus publishes in order and marks as published."""
    from dataclasses import replace
    bus = InMemoryBus()
    relay = OutboxRelay(bus)

    manager.upsert(sample_data)
    updated_data = replace(sample_data, internal_status="hired")
    manager.upsert(updated_data)

    count = relay.publish_pending()
    assert count == 2

    messages = bus.drain()
    assert len(messages) == 2
    assert messages[0][0] == "candidate.created"
    assert messages[1][0] == "candidate.updated"

    # All events should be marked as published
    assert OutboxEvent.objects.filter(published_at__isnull=True).count() == 0
