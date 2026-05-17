"""Redis Streams-backed event bus helpers.

This is intentionally small and best-effort for Phase 3 foundation work. The
canonical envelope lets us swap Redis Streams for Kafka/NATS later without
changing publishers.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.config import Settings
from app.services.events.envelope import EventEnvelope

_DEFAULT_STREAM = "nms:events"


class EventBus:
    """Tiny Redis Streams publisher/reader for canonical event envelopes."""

    def __init__(self, redis_url: str | None = None, stream_name: str | None = None) -> None:
        settings = Settings()
        self.redis_url = redis_url or settings.redis_url
        self.stream_name = stream_name or getattr(settings, "event_stream_name", _DEFAULT_STREAM)
        self._redis: Any = None

    async def _client(self) -> Any:
        if self._redis is not None:
            return self._redis
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self.redis_url, socket_timeout=2, decode_responses=True)
        return self._redis

    async def publish(self, envelope: EventEnvelope, *, maxlen: int = 10000) -> str | None:
        """Publish an event. Returns Redis stream id, or None when best-effort fails."""
        try:
            client = await self._client()
            payload = json.dumps(envelope.to_dict(), default=str, separators=(",", ":"))
            return await client.xadd(
                self.stream_name,
                {"event": payload, "event_type": envelope.event_type, "source": envelope.source},
                maxlen=maxlen,
                approximate=True,
            )
        except Exception as exc:
            logger.debug("EventBus publish failed for {}: {}", envelope.event_type, exc)
            return None

    async def read_latest(self, count: int = 100) -> list[tuple[str, EventEnvelope]]:
        """Read latest events from the stream for diagnostics/tests."""
        client = await self._client()
        rows = await client.xrevrange(self.stream_name, count=count)
        events: list[tuple[str, EventEnvelope]] = []
        for stream_id, fields in reversed(rows):
            raw = fields.get("event") if isinstance(fields, dict) else None
            if not raw:
                continue
            try:
                events.append((stream_id, EventEnvelope.from_dict(json.loads(raw))))
            except Exception as exc:
                logger.debug("EventBus read_latest skipped malformed event {}: {}", stream_id, exc)
        return events

    async def read_since(
        self,
        last_id: str = "0-0",
        *,
        count: int = 10,
        block_ms: int = 1000,
    ) -> list[tuple[str, EventEnvelope]]:
        """Read events newer than ``last_id``.

        This deliberately uses plain ``XREAD`` instead of consumer groups so the
        early worker skeletons are lab-friendly: no Redis bootstrap is required,
        tests can fake the call easily, and processors stay idempotent via the
        canonical ``event_id``.
        """
        client = await self._client()
        rows = await client.xread({self.stream_name: last_id}, count=count, block=block_ms)
        events: list[tuple[str, EventEnvelope]] = []
        for _stream, stream_rows in rows or []:
            for stream_id, fields in stream_rows:
                raw = fields.get("event") if isinstance(fields, dict) else None
                if not raw:
                    continue
                try:
                    events.append((stream_id, EventEnvelope.from_dict(json.loads(raw))))
                except Exception as exc:
                    logger.debug("EventBus read_since skipped malformed event {}: {}", stream_id, exc)
        return events

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception as exc:
            logger.debug("EventBus redis close failed: {}", exc)
        self._redis = None


async def publish_event(envelope: EventEnvelope, *, bus: EventBus | None = None) -> str | None:
    """Convenience one-shot publisher used by ingestion paths."""
    settings = Settings()
    if not settings.event_bus_enabled or settings.app_env == "test":
        return None

    own_bus = bus is None
    bus = bus or EventBus(redis_url=settings.redis_url, stream_name=settings.event_stream_name)
    try:
        return await bus.publish(envelope)
    finally:
        if own_bus:
            await bus.close()
