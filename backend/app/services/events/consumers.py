"""Defensive Redis Streams consumer skeletons for domain workers.

These consumers intentionally do only lightweight routing today. They make the
worker topology production-shaped without pretending full async processors exist
for every event type yet.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from loguru import logger

from app.services.events import EventBus, EventEnvelope


@dataclass(slots=True)
class ConsumerStats:
    seen: int = 0
    handled: int = 0
    skipped: int = 0
    errors: int = 0
    last_stream_id: str = "0-0"
    processed_event_ids: set[str] = field(default_factory=set)


class EventConsumer:
    """Base idempotent event consumer for worker skeletons."""

    worker_kind = "worker-events"
    event_prefixes: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self.stats = ConsumerStats()

    def accepts(self, event: EventEnvelope) -> bool:
        event_type = (event.event_type or "").lower()
        return event_type in self.event_types or any(event_type.startswith(prefix) for prefix in self.event_prefixes)

    async def handle(self, event: EventEnvelope) -> bool:
        """Handle a single event.

        Returns True when the skeleton claimed the event. Subclasses should keep
        this idempotent and side-effect safe.
        """
        if not self.accepts(event):
            return False
        logger.debug("{} accepted {} event_id={}", self.worker_kind, event.event_type, event.event_id)
        return True

    async def process_one(self, stream_id: str, event: EventEnvelope) -> bool:
        self.stats.last_stream_id = stream_id
        self.stats.seen += 1
        if event.event_id in self.stats.processed_event_ids:
            self.stats.skipped += 1
            return False
        try:
            handled = await self.handle(event)
            self.stats.processed_event_ids.add(event.event_id)
            if handled:
                self.stats.handled += 1
            else:
                self.stats.skipped += 1
            return handled
        except Exception as exc:  # pragma: no cover - defensive guard
            self.stats.errors += 1
            logger.warning("{} skipped failing event {}: {}", self.worker_kind, event.event_id, exc)
            return False

    async def poll_once(self, *, count: int = 10, block_ms: int = 1000) -> ConsumerStats:
        events = await self.bus.read_since(self.stats.last_stream_id, count=count, block_ms=block_ms)
        for stream_id, event in events:
            await self.process_one(stream_id, event)
        return self.stats

    async def run_forever(self, stop_event: asyncio.Event, *, idle_sleep_s: float = 1.0) -> None:
        while not stop_event.is_set():
            before = self.stats.seen
            await self.poll_once()
            if self.stats.seen == before:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=idle_sleep_s)
                except asyncio.TimeoutError:
                    pass

    async def close(self) -> None:
        await self.bus.close()


class AlarmEventConsumer(EventConsumer):
    worker_kind = "worker-alarm"
    event_prefixes = ("alarm", "trap", "syslog")
    event_types = ("linkdown", "linkup")


class DiscoveryEventConsumer(EventConsumer):
    worker_kind = "worker-discovery"
    event_prefixes = ("discovery", "inventory", "topology")


class TelemetryEventConsumer(EventConsumer):
    worker_kind = "worker-telemetry"
    event_prefixes = ("telemetry", "kpi", "gnmi")


def consumer_for_kind(kind: str, bus: EventBus | None = None) -> EventConsumer:
    mapping: dict[str, type[EventConsumer]] = {
        "worker-alarm": AlarmEventConsumer,
        "worker-discovery": DiscoveryEventConsumer,
        "worker-telemetry": TelemetryEventConsumer,
    }
    if kind not in mapping:
        raise ValueError(f"Unknown event consumer kind: {kind}")
    return mapping[kind](bus=bus)


EVENT_CONSUMER_KINDS: tuple[str, ...] = ("worker-alarm", "worker-discovery", "worker-telemetry")
