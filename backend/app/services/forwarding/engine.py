"""Northbound event forwarding engine."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.forwarding import ForwardingTarget

logger = logging.getLogger(__name__)

SEVERITY_RANK = {
    "critical": 5,
    "major": 4,
    "minor": 3,
    "warning": 2,
    "info": 1,
}


class ForwardingEngine:
    """Forward events to active external targets with a short-lived DB cache."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        cache_ttl_seconds: float = 30.0,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.session_factory = session_factory
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._cache: list[ForwardingTarget] = []
        self._cache_until = 0.0

    async def forward_event(self, event_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """Forward an event to every matching enabled target."""
        targets = await self._load_targets()
        matches = [target for target in targets if self._matches(target, event_dict)]
        results = []
        for target in matches:
            try:
                await self.send_to_target(target, event_dict, timeout_seconds=self.timeout_seconds)
                results.append({"target_id": str(target.id), "ok": True})
            except Exception as exc:  # pragma: no cover - defensive logging path
                logger.warning("Forwarding target %s failed: %s", target.name, exc)
                results.append({"target_id": str(target.id), "ok": False, "error": str(exc)})
        return results

    async def _load_targets(self) -> list[ForwardingTarget]:
        now = time.monotonic()
        if now < self._cache_until:
            return self._cache

        async with self.session_factory() as session:
            result = await session.execute(
                select(ForwardingTarget).where(ForwardingTarget.enabled.is_(True)).order_by(ForwardingTarget.name.asc())
            )
            self._cache = list(result.scalars().all())
            self._cache_until = now + self.cache_ttl_seconds
            return self._cache

    @staticmethod
    def _matches(target: ForwardingTarget, event: dict[str, Any]) -> bool:
        event_type = str(event.get("event_type") or event.get("type") or "").lower()
        if event_type not in target.event_types:
            return False
        if not target.severity_filter:
            return True
        event_severity = str(event.get("severity") or "info").lower()
        return SEVERITY_RANK.get(event_severity, 1) >= SEVERITY_RANK[target.severity_filter]

    @classmethod
    async def send_to_target(
        cls, target: ForwardingTarget, event: dict[str, Any], *, timeout_seconds: float = 3.0
    ) -> None:
        if target.protocol == "syslog_udp":
            await cls._send_udp(target, cls._syslog_packet(event), timeout_seconds)
        elif target.protocol == "syslog_tcp":
            await cls._send_tcp(target, cls._syslog_packet(event), timeout_seconds)
        elif target.protocol == "snmp_trap":
            await cls._send_snmp_trap(target, event, timeout_seconds)
        elif target.protocol == "http_webhook":
            await cls._send_http(target, event, timeout_seconds)
        else:
            raise ValueError(f"Unsupported forwarding protocol: {target.protocol}")

    @staticmethod
    def test_event() -> dict[str, Any]:
        return {
            "event_type": "alarm",
            "severity": "warning",
            "source": "nms-custom",
            "message": "NMS Custom forwarding test event",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @classmethod
    async def test_target(cls, target: ForwardingTarget, *, timeout_seconds: float = 3.0) -> tuple[bool, str]:
        try:
            await cls.send_to_target(target, cls.test_event(), timeout_seconds=timeout_seconds)
            return True, "Test event sent"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def _syslog_packet(event: dict[str, Any]) -> bytes:
        severity = str(event.get("severity") or "info").lower()
        severity_code = {"critical": 2, "major": 3, "minor": 4, "warning": 4, "info": 6}.get(severity, 6)
        pri = 16 * 8 + severity_code
        timestamp = datetime.now(UTC).isoformat()
        msg = str(event.get("message") or json.dumps(event, separators=(",", ":")))
        event_type = str(event.get("event_type") or event.get("type") or "event")
        return f"<{pri}>1 {timestamp} nms-custom nms-custom - - [nms event_type=\"{event_type}\" severity=\"{severity}\"] {msg}\n".encode()

    @staticmethod
    async def _send_udp(target: ForwardingTarget, payload: bytes, timeout_seconds: float) -> None:
        def send() -> None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(timeout_seconds)
                sock.sendto(payload, (target.target_host, target.target_port))

        await asyncio.to_thread(send)

    @staticmethod
    async def _send_tcp(target: ForwardingTarget, payload: bytes, timeout_seconds: float) -> None:
        def send() -> None:
            with socket.create_connection((target.target_host, target.target_port), timeout=timeout_seconds) as sock:
                sock.sendall(payload)

        await asyncio.to_thread(send)

    @staticmethod
    async def _send_http(target: ForwardingTarget, event: dict[str, Any], timeout_seconds: float) -> None:
        scheme = "http" if not target.target_host.startswith(("http://", "https://")) else ""
        base = f"{scheme}://{target.target_host}" if scheme else target.target_host
        url = f"{base}:{target.target_port}"
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(url, json=event)
            response.raise_for_status()

    @classmethod
    async def _send_snmp_trap(cls, target: ForwardingTarget, event: dict[str, Any], timeout_seconds: float) -> None:
        try:
            from pysnmp.hlapi.asyncio import (  # type: ignore[import-not-found]
                CommunityData,
                ContextData,
                NotificationType,
                ObjectIdentity,
                SnmpEngine,
                UdpTransportTarget,
                sendNotification,
            )
        except Exception:
            logger.info("pysnmp unavailable; sending best-effort SNMP trap marker over UDP")
            await cls._send_udp(target, json.dumps(event).encode(), timeout_seconds)
            return

        transport = await UdpTransportTarget.create((target.target_host, target.target_port), timeout=timeout_seconds)
        error_indication, *_ = await sendNotification(
            SnmpEngine(),
            CommunityData("public", mpModel=1),
            transport,
            ContextData(),
            "trap",
            NotificationType(ObjectIdentity("1.3.6.1.4.1.8072.2.3.0.1")),
        )
        if error_indication:
            raise RuntimeError(str(error_indication))
