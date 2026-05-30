"""Telemetry receiver skeleton for future gNMI/gRPC/MDT transports.

Phase 3D establishes the long-lived receiver boundary, heartbeat, and transport
interface. Actual protocol adapters can plug into ``TelemetryReceiver.run`` and
call ``TelemetryIngestionService.ingest_sample`` without changing runtime
service layout.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.telemetry.adapters import TelemetryAdapterError, parse_gnmi_json_frame
from app.services.telemetry.ingestion import TelemetryIngestionService

SessionFactory = Callable[[], AsyncSession]


@dataclass(slots=True)
class TelemetryReceiverConfig:
    transport: str = "gnmi"
    bind_host: str = "0.0.0.0"  # nosec B104 - container listener; exposure controlled by Compose/K8s/firewall.
    bind_port: int = 57400
    idle_heartbeat_seconds: int = 30
    # Maximum bytes read per TCP frame/line. Prevents memory exhaustion from a
    # single malformed or malicious client sending an unbounded line.
    # Defaults to MAX_BULK_REQUEST_BODY_MB (same envelope as API bulk endpoints).
    max_frame_bytes: int = 0  # 0 = derive from settings at runtime


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
        if self.config.transport.lower() in {"gnmi-json", "mdt-json", "json"}:
            await self._run_json_line_server(stop_event)
            return
        logger.warning(
            "Telemetry transport {} has no local protocol server yet; use gnmi-json for line-delimited gNMI/MDT frames",
            self.config.transport,
        )
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.config.idle_heartbeat_seconds)
            except TimeoutError:
                logger.debug("Telemetry receiver idle heartbeat transport={}", self.config.transport)

    async def _run_json_line_server(self, stop_event: asyncio.Event) -> None:
        """Run a lightweight TCP line-delimited JSON telemetry adapter."""
        server = await asyncio.start_server(self._handle_client, self.config.bind_host, self.config.bind_port)
        logger.info("Telemetry JSON adapter listening on {}:{}", self.config.bind_host, self.config.bind_port)
        async with server:
            server_task = asyncio.create_task(server.serve_forever())
            try:
                await stop_event.wait()
            finally:
                server.close()
                await server.wait_closed()
                server_task.cancel()

    def _effective_max_frame_bytes(self) -> int:
        """Return the effective per-frame byte limit from config or settings."""
        if self.config.max_frame_bytes > 0:
            return self.config.max_frame_bytes
        return int(settings.max_bulk_request_body_mb * 1024 * 1024)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        max_frame = self._effective_max_frame_bytes()
        try:
            while line := await reader.readline():
                if len(line) > max_frame:
                    logger.warning(
                        "Telemetry receiver: frame from {} exceeded {} bytes ({} bytes), closing connection",
                        peer,
                        max_frame,
                        len(line),
                    )
                    writer.write(b"ERR frame too large\n")
                    await writer.drain()
                    break
                try:
                    samples = parse_gnmi_json_frame(line)
                    for sample in samples:
                        await self.ingestion.ingest_sample(sample)
                    writer.write(f"OK {len(samples)}\n".encode())
                    await writer.drain()
                except TelemetryAdapterError as exc:
                    logger.warning("Telemetry adapter rejected frame from {}: {}", peer, exc)
                    writer.write(f"ERR {exc}\n".encode())
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
