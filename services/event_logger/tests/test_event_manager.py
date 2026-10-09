"""T4: Event manager dedup tests."""
import os
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("EVENT_BUS_BACKEND", "memory")

import django
django.setup()

from event_logger.managers.event_manager import EventManager, RecordResult
from event_logger.event_consumers.candidate_events import CandidateEventsConsumer
from event_logger.db_models.models import ProcessedEvent
from klaaryo_bus.in_memory import InMemoryBus


@pytest.fixture
def manager():
    return EventManager()


@pytest.fixture
def sample_payload():
    return {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "candidate.created",
        "occurred_at": "2026-10-01T12:00:00Z",
        "candidate_pk": 1,
        "ats_source": "alpha",
        "external_id": "test-001",
        "changed_fields": [],
    }


@pytest.mark.django_db(transaction=True)
def test_record_processed_then_duplicate(manager, sample_payload):
    """Same event_id twice -> PROCESSED then DUPLICATE, one row in table."""
    result1 = manager.record(sample_payload)
    assert result1 == RecordResult.PROCESSED

    result2 = manager.record(sample_payload)
    assert result2 == RecordResult.DUPLICATE

    assert ProcessedEvent.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_consumer_output(manager, sample_payload, capsys):
    """Verify [PROCESSED] and [SKIPPED] output lines."""
    bus = InMemoryBus()
    bus.publish("candidate.created", sample_payload)
    bus.publish("candidate.created", sample_payload)  # duplicate

    consumer = CandidateEventsConsumer(bus, manager)
    # Manually call handler for each message
    for topic, payload in [("candidate.created", sample_payload), ("candidate.created", sample_payload)]:
        consumer._handle(topic, payload)

    captured = capsys.readouterr()
    assert "[PROCESSED]" in captured.out
    assert "[SKIPPED]" in captured.out
    assert "duplicate" in captured.out
