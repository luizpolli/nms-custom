"""Alarm correlator — classifies SNMP traps and manages alarm lifecycle.

Handles deduplication (occurrence_count), clearing (linkUp clears linkDown),
and acknowledgement.  All DB access is async through the session factory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.device import Device
from app.services.alarms.rules import AlarmRuleContext, apply_rule, find_matching_rule, normalize_alarm_severity
from app.services.events import EventEnvelope, publish_event
from app.services.snmp.trap_receiver import TrapEvent

# Well-known trap OIDs (no leading dot)
_LINK_DOWN = "1.3.6.1.6.3.1.1.5.3"
_LINK_UP = "1.3.6.1.6.3.1.1.5.4"
_COLD_START = "1.3.6.1.6.3.1.1.5.1"
_WARM_START = "1.3.6.1.6.3.1.1.5.2"
_AUTH_FAILURE = "1.3.6.1.6.3.1.1.5.5"

# ifIndex OID prefix (ifIndex column, table 2.2.1.1)
_IF_INDEX_PREFIX = "1.3.6.1.2.1.2.2.1.1."

SessionFactory = Callable[[], AsyncSession]


def _extract_if_index(varbinds: dict[str, str]) -> str:
    """Return ifIndex extracted from a varbind OID suffix, or 'unknown'."""
    for oid in varbinds:
        if oid.startswith(_IF_INDEX_PREFIX):
            return oid[len(_IF_INDEX_PREFIX):]
    return "unknown"


class AlarmCorrelator:
    """Classify SNMP traps and maintain the alarm table with correlation logic."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, event: TrapEvent) -> dict:
        """Pure classification — no DB.  Returns classification dict."""
        oid = (event.trap_oid or "").strip()
        host = event.source_host

        if oid == _LINK_DOWN:
            idx = _extract_if_index(event.varbinds)
            return {
                "severity": "major",
                "category": "link",
                "event_type": "linkDown",
                "message": f"Link down on {host} interface {idx}",
                "correlation_key": f"link:{host}:{idx}",
            }

        if oid == _LINK_UP:
            idx = _extract_if_index(event.varbinds)
            return {
                "severity": "clear",
                "category": "link",
                "event_type": "linkUp",
                "message": f"Link restored on {host} interface {idx}",
                "correlation_key": f"link:{host}:{idx}",
            }

        if oid == _COLD_START:
            return {
                "severity": "major",
                "category": "device",
                "event_type": "coldStart",
                "message": f"Cold start (reboot) detected on {host}",
                "correlation_key": f"device:{host}:reboot",
            }

        if oid == _WARM_START:
            return {
                "severity": "warning",
                "category": "device",
                "event_type": "warmStart",
                "message": f"Warm start detected on {host}",
                "correlation_key": f"device:{host}:reboot",
            }

        if oid == _AUTH_FAILURE:
            return {
                "severity": "warning",
                "category": "auth",
                "event_type": "authenticationFailure",
                "message": f"SNMP authentication failure from {host}",
                "correlation_key": f"auth:{host}",
            }

        return {
            "severity": "info",
            "category": "other",
            "event_type": oid or "unknown",
            "message": f"Unknown trap {oid!r} from {host}",
            "correlation_key": f"other:{host}:{oid}",
        }

    async def handle_trap(self, event: TrapEvent) -> Alarm | None:
        """Classify trap, then create / update / clear the matching alarm row."""
        return await self._handle_classified_event(
            source_type="snmp_trap",
            source_host=event.source_host,
            trap_oid=event.trap_oid,
            varbinds=event.varbinds,
            cls=self.classify(event),
        )

    async def handle_syslog(
        self,
        *,
        source_host: str,
        message: str,
        severity: str = "info",
        category: str = "syslog",
        facility: str | None = None,
        correlation_key: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> Alarm | None:
        """Create/update/clear an alarm from a syslog message after applying rules."""
        metadata = dict(fields or {})
        if facility:
            metadata["facility"] = facility
        return await self._handle_classified_event(
            source_type="syslog",
            source_host=source_host,
            trap_oid=None,
            varbinds=metadata,
            cls={
                "severity": normalize_alarm_severity(severity),
                "category": category,
                "event_type": facility or "syslog",
                "message": message,
                "correlation_key": correlation_key or f"syslog:{source_host}:{facility or 'message'}:{message[:80]}",
            },
        )

    async def handle_event(
        self,
        *,
        source_host: str,
        event_type: str,
        message: str,
        severity: str = "info",
        category: str = "custom",
        correlation_key: str | None = None,
        fields: dict[str, str] | None = None,
    ) -> Alarm | None:
        """Create/update/clear an alarm from an internal/custom event after applying rules."""
        return await self._handle_classified_event(
            source_type="event",
            source_host=source_host,
            trap_oid=None,
            varbinds=dict(fields or {}),
            cls={
                "severity": normalize_alarm_severity(severity),
                "category": category,
                "event_type": event_type,
                "message": message,
                "correlation_key": correlation_key or f"event:{source_host}:{event_type}",
            },
        )

    async def _handle_classified_event(
        self,
        *,
        source_type: str,
        source_host: str,
        trap_oid: str | None,
        varbinds: dict[str, str],
        cls: dict[str, Any],
    ) -> Alarm | None:
        """Apply customer rules and maintain the alarm table for any event source."""
        now = datetime.now(timezone.utc)

        async with self._sf() as session:
            ctx = AlarmRuleContext(
                source_type=source_type,
                source_host=source_host,
                trap_oid=trap_oid,
                event_type=cls["event_type"],
                category=cls["category"],
                message=cls["message"],
                severity=cls["severity"],
                varbinds=varbinds,
                correlation_key=cls["correlation_key"],
            )
            rule = await find_matching_rule(session, ctx)
            if rule is not None:
                cls = apply_rule(cls, rule, ctx)
                logger.debug(
                    "Alarm rule matched: {} ({}) auto_clear={}",
                    cls["matched_rule_name"],
                    cls["matched_rule_id"],
                    cls["auto_clear"],
                )

            device = await self._find_device_by_host(session, source_host)
            device_id = str(device.id) if device is not None else None

            await publish_event(
                EventEnvelope(
                    event_type=cls["event_type"],
                    source=source_type,
                    severity=cls["severity"],
                    device_id=device_id,
                    object_type="alarm",
                    object_id=cls["correlation_key"],
                    payload={
                        "source_host": source_host,
                        "category": cls["category"],
                        "message": cls["message"],
                        "correlation_key": cls["correlation_key"],
                        "trap_oid": trap_oid,
                        "fields": varbinds,
                    },
                )
            )

            if cls["severity"] == "clear":
                return await self._apply_clear(session, cls["correlation_key"], now)

            alarm = await self._find_active(session, cls["correlation_key"])
            if alarm is not None:
                alarm.occurrence_count += 1
                alarm.last_seen = now
                alarm.severity = cls["severity"]
                alarm.category = cls["category"]
                alarm.event_type = cls["event_type"]
                alarm.message = cls["message"]
                alarm.raw_varbinds = self._raw_payload(varbinds, cls)
                if device is not None and alarm.device_id != device.id:
                    alarm.device_id = device.id
                    alarm.object_type = alarm.object_type or "device"
                    alarm.object_id = alarm.object_id or str(device.id)
                await session.commit()
                logger.debug("Alarm deduped: {} ({}x)", cls["correlation_key"], alarm.occurrence_count)
                return alarm

            alarm = Alarm(
                id=uuid.uuid4(),
                device_id=device.id if device is not None else None,
                source_host=source_host,
                severity=cls["severity"],
                category=cls["category"],
                event_type=cls["event_type"],
                message=cls["message"],
                trap_oid=trap_oid,
                raw_varbinds=self._raw_payload(varbinds, cls),
                correlation_key=cls["correlation_key"],
                dedup_key=cls["correlation_key"],
                source_type=source_type,
                object_type="device",
                object_id=str(device.id) if device is not None else None,
                state="active",
                first_seen=now,
                last_seen=now,
                created_at=now,
            )
            session.add(alarm)
            await session.commit()
            logger.info("Alarm created: {} sev={}", cls["correlation_key"], cls["severity"])
            return alarm

    async def _find_device_by_host(self, session: AsyncSession, host: str) -> Device | None:
        if not host:
            return None
        result = await session.execute(
            select(Device)
            .where((Device.ip_address == host) | (Device.name == host))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def ack(self, alarm_id: uuid.UUID, by_user: str) -> Alarm:
        """Acknowledge an alarm."""
        async with self._sf() as session:
            alarm = await session.get(Alarm, alarm_id)
            if alarm is None:
                raise ValueError(f"Alarm {alarm_id} not found")
            alarm.state = "acknowledged"
            alarm.ack_by = by_user
            alarm.last_seen = datetime.now(timezone.utc)
            await session.commit()
            return alarm

    async def clear(self, alarm_id: uuid.UUID) -> Alarm:
        """Manually clear an alarm by id."""
        async with self._sf() as session:
            alarm = await session.get(Alarm, alarm_id)
            if alarm is None:
                raise ValueError(f"Alarm {alarm_id} not found")
            now = datetime.now(timezone.utc)
            alarm.state = "cleared"
            alarm.cleared_at = now
            alarm.last_seen = now
            await session.commit()
            return alarm

    async def list_active(
        self,
        device_id: uuid.UUID | None = None,
        severity: str | None = None,
    ) -> list[Alarm]:
        """Return active alarms, optionally filtered."""
        async with self._sf() as session:
            stmt = select(Alarm).where(Alarm.state == "active")
            if device_id is not None:
                stmt = stmt.where(Alarm.device_id == device_id)
            if severity is not None:
                stmt = stmt.where(Alarm.severity == severity)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _find_active(self, session: AsyncSession, correlation_key: str) -> Alarm | None:
        stmt = (
            select(Alarm)
            .where(Alarm.correlation_key == correlation_key, Alarm.state == "active")
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _apply_clear(
        self, session: AsyncSession, correlation_key: str, now: datetime
    ) -> Alarm | None:
        alarm = await self._find_active(session, correlation_key)
        if alarm is None:
            logger.debug("Clear event for {} — no active alarm found", correlation_key)
            return None
        alarm.state = "cleared"
        alarm.cleared_at = now
        alarm.last_seen = now
        await session.commit()
        logger.info("Alarm cleared: {}", correlation_key)
        return alarm

    @staticmethod
    def _raw_payload(varbinds: dict[str, str], cls: dict[str, Any]) -> dict[str, str]:
        payload = dict(varbinds)
        if cls.get("matched_rule_id"):
            payload["_matched_rule_id"] = str(cls["matched_rule_id"])
            payload["_matched_rule_name"] = str(cls["matched_rule_name"])
        return payload
