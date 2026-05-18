"""Redis Streams consumers for domain workers.

The consumers keep delivery/ACK semantics in one place and run small, idempotent
domain processors for events that already have a concrete local workflow.
"""

from __future__ import annotations

import asyncio
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import async_session_factory
from app.models.alarm import Alarm
from app.models.device import Device
from app.services.events import EventBus, EventEnvelope

SessionFactory = Callable[[], AsyncSession]


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
        session_factory: SessionFactory | None = None,
    ) -> None:
        settings = Settings()
        self.bus = bus or EventBus()
        self.session_factory = session_factory or async_session_factory
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

    def accepts(self, event: EventEnvelope) -> bool:
        if super().accepts(event):
            return True
        return event.source in {"syslog", "trap"} or event.object_type == "alarm"

    async def handle(self, event: EventEnvelope) -> bool:
        if not await super().handle(event):
            return False
        enriched = await self._enrich_alarm(event)
        if enriched:
            logger.debug("{} enriched alarm for event_id={}", self.worker_kind, event.event_id)
        return True

    async def _enrich_alarm(self, event: EventEnvelope) -> bool:
        """Attach known device metadata to an active alarm when possible."""
        correlation_key = str(event.object_id or event.payload.get("correlation_key") or "")
        source_host = str(event.payload.get("source_host") or "")
        if not correlation_key and not source_host:
            return False

        async with self.session_factory() as session:
            alarm = await self._find_alarm(session, correlation_key, source_host)
            if alarm is None:
                return False
            device = await self._find_device(session, event, source_host)
            changed = False
            if device is not None and alarm.device_id != device.id:
                alarm.device_id = device.id
                alarm.object_type = alarm.object_type or "device"
                alarm.object_id = alarm.object_id or str(device.id)
                changed = True
            if event.source and alarm.source_type != event.source:
                alarm.source_type = event.source
                changed = True
            if changed:
                await session.commit()
            return changed

    async def _find_alarm(self, session: AsyncSession, correlation_key: str, source_host: str) -> Alarm | None:
        clauses = []
        if correlation_key:
            clauses.append(Alarm.correlation_key == correlation_key)
        if source_host:
            clauses.append(Alarm.source_host == source_host)
        if not clauses:
            return None
        result = await session.execute(
            select(Alarm)
            .where(Alarm.state == "active", or_(*clauses))
            .order_by(Alarm.last_seen.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_device(self, session: AsyncSession, event: EventEnvelope, source_host: str) -> Device | None:
        if event.device_id:
            try:
                device = await session.get(Device, uuid.UUID(str(event.device_id)))
                if device is not None:
                    return device
            except ValueError:
                pass
        if not source_host:
            return None
        result = await session.execute(
            select(Device)
            .where(or_(Device.ip_address == source_host, Device.name == source_host))
            .limit(1)
        )
        return result.scalar_one_or_none()


class DiscoveryEventConsumer(EventConsumer):
    worker_kind = "worker-discovery"
    event_prefixes = ("discovery", "inventory", "topology")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Per-instance cache: device_id str -> last known status str
        self._last_status: dict[str, str] = {}

    async def handle(self, event: EventEnvelope) -> bool:
        if not await super().handle(event):
            return False
        prev_status, updated = await self._apply_device_status(event)
        if updated:
            logger.debug("{} updated discovery device state for event_id={}", self.worker_kind, event.event_id)
        await self._maybe_emit_refresh(event, prev_status)
        return True

    async def _apply_device_status(self, event: EventEnvelope) -> tuple[str | None, bool]:
        payload = event.payload or {}
        status = payload.get("status") or payload.get("device_status")
        if status not in {"up", "down", "unknown", "degraded"}:
            return None, False

        async with self.session_factory() as session:
            device = None
            raw_device_id = event.device_id or payload.get("device_id")
            if raw_device_id:
                try:
                    device = await session.get(Device, uuid.UUID(str(raw_device_id)))
                except ValueError:
                    device = None
            if device is None and payload.get("ip_address"):
                result = await session.execute(select(Device).where(Device.ip_address == str(payload["ip_address"])).limit(1))
                device = result.scalar_one_or_none()
            if device is None:
                return None, False
            prev_status = str(device.status) if device.status else None
            device.status = str(status)
            device.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return prev_status, True

    async def _maybe_emit_refresh(self, event: EventEnvelope, prev_status: str | None) -> None:
        """Publish a discovery.refresh.requested signal when a device becomes up.

        Idempotent: uses _last_status to skip re-emission when the previous status
        was already 'up' (i.e., no real transition happened).
        """
        payload = event.payload or {}
        status = payload.get("status") or payload.get("device_status")
        refresh_requested = bool(payload.get("refresh_requested"))

        raw_device_id = str(event.device_id or payload.get("device_id") or "")
        if not raw_device_id:
            return

        # Idempotency guard using cached last-seen status
        last_known = self._last_status.get(raw_device_id)
        became_up = status == "up" and (last_known or prev_status) not in {"up"}
        if not became_up and not refresh_requested:
            self._last_status[raw_device_id] = str(status) if status else last_known or ""
            return

        self._last_status[raw_device_id] = str(status) if status else ""
        reason = "refresh_requested" if refresh_requested else f"status_transition:{prev_status}->{status}"
        refresh_event = EventEnvelope(
            event_type="discovery.refresh.requested",
            source=self.worker_kind,
            device_id=raw_device_id,
            trace_id=event.trace_id,
            payload={
                "device_id": raw_device_id,
                "correlation_key": str(event.object_id or payload.get("correlation_key") or ""),
                "reason": reason,
            },
        )
        await self.bus.publish(refresh_event)


class TelemetryEventConsumer(EventConsumer):
    worker_kind = "worker-telemetry"
    event_prefixes = ("telemetry", "kpi", "gnmi")

    async def handle(self, event: EventEnvelope) -> bool:
        if not await super().handle(event):
            return False
        evaluated = await self._evaluate_thresholds(event)
        if evaluated:
            logger.debug("{} evaluated {} TCA event(s) for event_id={}", self.worker_kind, evaluated, event.event_id)
        return True

    async def _evaluate_thresholds(self, event: EventEnvelope) -> int:
        if (event.event_type or "").lower() != "telemetry.sample.normalized":
            return 0
        kpi_id = event.payload.get("kpi_id")
        if kpi_id is None:
            return 0
        from app.models.kpi import KPI
        from app.services.kpi.thresholds import KPIThresholdEvaluator

        async with self.session_factory() as session:
            kpi = await session.get(KPI, int(kpi_id))
        if kpi is None:
            return 0
        evaluator = KPIThresholdEvaluator(self.session_factory)
        tca_count = await evaluator.evaluate([kpi])
        await self._emit_kpi_evaluated(event, kpi_id, tca_count)
        return tca_count

    async def _emit_kpi_evaluated(self, event: EventEnvelope, kpi_id: int, tca_count: int) -> None:
        """Fan-out a telemetry.kpi.evaluated event after threshold evaluation."""
        severity = "nominal" if tca_count == 0 else "warning"
        fan_out = EventEnvelope(
            event_type="telemetry.kpi.evaluated",
            source=self.worker_kind,
            device_id=event.device_id or str(event.payload.get("device_id") or ""),
            trace_id=event.trace_id,
            severity=severity,
            payload={
                "kpi_id": kpi_id,
                "device_id": event.device_id or str(event.payload.get("device_id") or ""),
                "value": event.payload.get("value"),
                "severity": severity,
            },
        )
        await self.bus.publish(fan_out)


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
