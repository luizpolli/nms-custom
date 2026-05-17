"""Telemetry receiver skeleton for future gNMI/gRPC/MDT transports.

Phase 3D establishes the long-lived receiver boundary, heartbeat, and transport
interface. Actual protocol adapters can plug into ``TelemetryReceiver.run`` and
call ``TelemetryIngestionService.ingest_sample`` without changing runtime
service layout.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.telemetry.ingestion import TelemetryIngestionService

SessionFactory = Callable[[], AsyncSession]


@dataclass(slots=True)
class TelemetryReceiverConfig:
    transport: str = "gnmi"
    bind_host: str = "0.0.0.0"  # nosec B104 - container listener; exposure controlled by Compose/K8s/firewall.
    bind_port: int = 57400
    idle_heartbeat_seconds: int = 30


class TelemetryReceiver:
    """Long-lived telemetry receiver runtime placeholder.

    The current implementation is intentionally idle-safe: it owns the service
    lifecycle and ingestion service, logs readiness, and waits until stopped.
    Protocol-specific gNMI/gRPC/MDT adapters should be added behind this class.
    """

    def __init__(self, session_factory: SessionFactory, config: TelemetryReceiverConfig | None = None) -> None:
        self.session_factory = session_factory
        self.config = config or TelemetryReceiverConfig()
        self.ingestion = TelemetryIngestionService(session_factory)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Telemetry receiver ready transport={} bind={}:{}",
            self.config.transport,
            self.config.bind_host,
            self.config.bind_port,
        )
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.config.idle_heartbeat_seconds)
            except asyncio.TimeoutError:
                logger.debug("Telemetry receiver idle heartbeat transport={}", self.config.transport)
