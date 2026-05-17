"""Defensive Redis Streams consumer skeletons for domain workers.

These consumers intentionally do only lightweight routing today. They make the
worker topology production-shaped without pretending full async processors exist
for every event type yet.
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass, field
from loguru import logger

from app.config import Settings
from app.services.events import EventBus, EventEnvelope


@dataclass(slots=True)
class ConsumerStats:
    seen: int = 0
    handled: int = 0
    skipped: int = 0
    errors: int = 0
    acked: int = 0
    claimed: int = 0
    last_stream_id: str = "0-0"
    processed_event_ids: set[str] = field(default_factory=set)


class EventConsumer:
    """Base idempotent event consumer for worker skeletons."""

    worker_kind = "worker-events"
    event_prefixes: tuple[str, ...] = ()
    event_types: tuple[str, ...] = ()

    def __init__(
        self,
        bus: EventBus | None = None,
        *,
        group_name: str | None = None,
        consumer_name: str | None = None,
        use_consumer_group: bool = True,
    ) -> None:
        settings = Settings()
        self.bus = bus or EventBus()
        self.group_name = group_name or f"{settings.event_consumer_group_prefix}:{self.worker_kind}"
        self.consumer_name = consumer_name or f"{socket.gethostname()}:{self.worker_kind}"
        self.use_consumer_group = use_consumer_group
        self.stale_ms = settings.event_consumer_stale_ms
        self.stats = ConsumerStats()
        self._group_ready = False

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
        if self.use_consumer_group:
            if not self._group_ready:
                await self.bus.ensure_consumer_group(self.group_name)
                self._group_ready = True
            events = await self.bus.claim_stale(
                self.group_name,
                self.consumer_name,
                min_idle_ms=self.stale_ms,
                count=count,
            )
            if events:
                self.stats.claimed += len(events)
            else:
                events = await self.bus.read_group(
                    self.group_name,
                    self.consumer_name,
                    count=count,
                    block_ms=block_ms,
                )
        else:
            events = await self.bus.read_since(self.stats.last_stream_id, count=count, block_ms=block_ms)

        for stream_id, event in events:
            errors_before = self.stats.errors
            await self.process_one(stream_id, event)
            if self.use_consumer_group and self.stats.errors == errors_before:
                self.stats.acked += await self.bus.ack(self.group_name, stream_id)
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


def consumer_for_kind(kind: str, bus: EventBus | None = None, **kwargs) -> EventConsumer:
    mapping: dict[str, type[EventConsumer]] = {
        "worker-alarm": AlarmEventConsumer,
        "worker-discovery": DiscoveryEventConsumer,
        "worker-telemetry": TelemetryEventConsumer,
    }
    if kind not in mapping:
        raise ValueError(f"Unknown event consumer kind: {kind}")
    return mapping[kind](bus=bus, **kwargs)


EVENT_CONSUMER_KINDS: tuple[str, ...] = ("worker-alarm", "worker-discovery", "worker-telemetry")
