"""Outbox relay: publishes pending events to the event bus."""
from __future__ import annotations

import logging
import time
import threading
from datetime import datetime, timezone

from talent_pool.db_models.models import OutboxEvent

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self, publisher) -> None:
        self._publisher = publisher

    def publish_pending(self, batch: int = 100) -> int:
        """Publish up to `batch` pending events. Returns number published."""
        pending = OutboxEvent.objects.filter(
            published_at__isnull=True,
        ).order_by("id")[:batch]

        count = 0
        for event in pending:
            try:
                self._publisher.publish(event.topic, event.payload)
                event.published_at = datetime.now(timezone.utc)
                event.save(update_fields=["published_at"])
                count += 1
                logger.info(
                    "Published event %s (topic=%s)", event.event_id, event.topic,
                )
            except Exception:
                logger.exception(
                    "Failed to publish event %s, stopping relay batch",
                    event.event_id,
                )
                break
        return count

    def run_forever(self, interval: float = 0.5) -> None:
        """Run the relay loop in the current thread."""
        logger.info("Outbox relay started (interval=%.1fs)", interval)
        while True:
            try:
                self.publish_pending()
            except Exception:
                logger.exception("Relay loop error")
            time.sleep(interval)

    def start_daemon(self, interval: float = 0.5) -> threading.Thread:
        """Start the relay loop in a daemon thread."""
        t = threading.Thread(
            target=self.run_forever,
            args=(interval,),
            daemon=True,
            name="outbox-relay",
        )
        t.start()
        return t

    @staticmethod
    def mark_for_republish(event_id: str | None = None, last: bool = False) -> None:
        """Reset published_at so the relay re-publishes the event."""
        if last:
            event = OutboxEvent.objects.filter(
                published_at__isnull=False,
            ).order_by("-id").first()
        elif event_id:
            event = OutboxEvent.objects.filter(event_id=event_id).first()
        else:
            raise ValueError("Provide event_id or last=True")

        if event is None:
            raise ValueError("No matching event found")

        event.published_at = None
        event.save(update_fields=["published_at"])
        logger.info("Marked event %s for republish", event.event_id)
