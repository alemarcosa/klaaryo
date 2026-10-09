"""In-memory event bus for testing."""
from __future__ import annotations

from collections.abc import Callable, Sequence


class InMemoryBus:
    """Implements both EventPublisher and EventSubscriber for testing."""

    def __init__(self) -> None:
        self._messages: list[tuple[str, dict]] = []
        self._handler: Callable[[str, dict], None] | None = None

    def publish(self, topic: str, payload: dict) -> None:
        self._messages.append((topic, payload))

    def drain(self) -> list[tuple[str, dict]]:
        """Return and clear all published messages (synchronous, for tests)."""
        msgs = list(self._messages)
        self._messages.clear()
        return msgs

    def run(self, topics: Sequence[str], handler: Callable[[str, dict], None]) -> None:
        """Process all buffered messages and block (for test use, call drain() instead)."""
        self._handler = handler
        for topic, payload in self._messages:
            if topic in topics:
                handler(topic, payload)
