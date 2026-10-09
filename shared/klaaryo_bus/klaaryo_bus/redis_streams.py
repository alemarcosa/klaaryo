"""Redis Streams adapter for the event bus."""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence

import redis

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "event_logger"
CONSUMER_NAME = "worker-1"
STARTUP_RETRY_PAUSE = 2.0
STARTUP_MAX_RETRIES = 30


class RedisPublisher:
    def __init__(self, redis_url: str) -> None:
        self._r = redis.Redis.from_url(redis_url, decode_responses=True)

    def publish(self, topic: str, payload: dict) -> None:
        self._r.xadd(topic, {"payload": json.dumps(payload)})


class RedisSubscriber:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._r: redis.Redis | None = None

    def _connect(self) -> redis.Redis:
        for attempt in range(1, STARTUP_MAX_RETRIES + 1):
            try:
                r = redis.Redis.from_url(self._redis_url, decode_responses=True)
                r.ping()
                logger.info("Connected to Redis on attempt %d", attempt)
                return r
            except redis.ConnectionError:
                logger.warning(
                    "Redis not ready (attempt %d/%d), retrying in %.0fs...",
                    attempt, STARTUP_MAX_RETRIES, STARTUP_RETRY_PAUSE,
                )
                time.sleep(STARTUP_RETRY_PAUSE)
        raise RuntimeError("Could not connect to Redis")

    def _ensure_groups(self, r: redis.Redis, topics: Sequence[str]) -> None:
        for topic in topics:
            try:
                r.xgroup_create(topic, CONSUMER_GROUP, id="0", mkstream=True)
                logger.info("Created consumer group '%s' on '%s'", CONSUMER_GROUP, topic)
            except redis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    def run(self, topics: Sequence[str], handler: Callable[[str, dict], None]) -> None:
        r = self._connect()
        self._r = r
        self._ensure_groups(r, topics)

        stream_keys = {topic: ">" for topic in topics}

        # First pass: re-read own pending messages
        pending_keys = {topic: "0" for topic in topics}
        while True:
            results = r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, pending_keys, count=100,
            )
            if not results or all(len(msgs) == 0 for _, msgs in results):
                break
            self._process_results(r, results, handler)

        # Main loop
        logger.info("Entering main consume loop on topics: %s", list(topics))
        while True:
            results = r.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, stream_keys, count=100, block=5000,
            )
            if results:
                self._process_results(r, results, handler)

    def _process_results(
        self,
        r: redis.Redis,
        results: list,
        handler: Callable[[str, dict], None],
    ) -> None:
        for topic, messages in results:
            for msg_id, fields in messages:
                raw = fields.get("payload", "")
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    logger.error(
                        "[ERROR] Poison message on %s id=%s: unparsable JSON: %s",
                        topic, msg_id, raw,
                    )
                    r.xack(topic, CONSUMER_GROUP, msg_id)
                    continue

                handler(topic, payload)
                r.xack(topic, CONSUMER_GROUP, msg_id)
