"""Bus factory: creates publisher/subscriber from environment."""
from __future__ import annotations

import os

from klaaryo_bus.in_memory import InMemoryBus
from klaaryo_bus.redis_streams import RedisPublisher, RedisSubscriber

_memory_bus: InMemoryBus | None = None


def _get_memory_bus() -> InMemoryBus:
    global _memory_bus
    if _memory_bus is None:
        _memory_bus = InMemoryBus()
    return _memory_bus


def publisher_from_env() -> RedisPublisher | InMemoryBus:
    backend = os.environ.get("EVENT_BUS_BACKEND", "redis")
    if backend == "memory":
        return _get_memory_bus()
    return RedisPublisher(os.environ["REDIS_URL"])


def subscriber_from_env() -> RedisSubscriber | InMemoryBus:
    backend = os.environ.get("EVENT_BUS_BACKEND", "redis")
    if backend == "memory":
        return _get_memory_bus()
    return RedisSubscriber(os.environ["REDIS_URL"])
