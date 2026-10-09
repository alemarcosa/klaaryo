"""Protocol definitions for the event bus."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol


class EventPublisher(Protocol):
    def publish(self, topic: str, payload: dict) -> None: ...


class EventSubscriber(Protocol):
    def run(self, topics: Sequence[str], handler: Callable[[str, dict], None]) -> None:
        """Block and consume messages.

        Contract: ack ONLY if handler returns normally.
        If handler raises, no ack → redelivery.
        """
        ...
