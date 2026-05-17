"""Async UDP syslog receiver with RFC5424/BSD-ish parsing."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from loguru import logger

SYSLOG_SEVERITIES = {
    0: "emerg",
    1: "alert",
    2: "critical",
    3: "error",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}

_RFC5424_RE = re.compile(
    r"^<(?P<pri>\d{1,3})>(?P<version>\d+)\s+"
    r"(?P<timestamp>\S+)\s+(?P<hostname>\S+)\s+"
    r"(?P<app>\S+)\s+(?P<procid>\S+)\s+(?P<msgid>\S+)\s+"
    r"(?P<structured_data>-|\[[^\]]*\])(?:\s+(?P<message>.*))?$"
)
_BSD_RE = re.compile(r"^<(?P<pri>\d{1,3})>(?P<message>.*)$", re.DOTALL)


@dataclass(slots=True)
class SyslogEvent:
    source_host: str
    source_port: int
    facility: int | None
    severity: str
    message: str
    app_name: str | None = None
    msg_id: str | None = None
    structured_data: str | None = None
    raw: str = ""
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


SyslogHandler = Callable[[SyslogEvent], Awaitable[None] | None]


def parse_syslog(payload: bytes, source_host: str, source_port: int) -> SyslogEvent:
    raw = payload.decode("utf-8", errors="replace").strip("\x00\r\n")
    match = _RFC5424_RE.match(raw)
    if match:
        pri = int(match.group("pri"))
        return SyslogEvent(
            source_host=source_host,
            source_port=source_port,
            facility=pri // 8,
            severity=SYSLOG_SEVERITIES.get(pri % 8, "info"),
            message=match.group("message") or "",
            app_name=None if match.group("app") == "-" else match.group("app"),
            msg_id=None if match.group("msgid") == "-" else match.group("msgid"),
            structured_data=None if match.group("structured_data") == "-" else match.group("structured_data"),
            raw=raw,
        )

    match = _BSD_RE.match(raw)
    if match:
        pri = int(match.group("pri"))
        return SyslogEvent(
            source_host=source_host,
            source_port=source_port,
            facility=pri // 8,
            severity=SYSLOG_SEVERITIES.get(pri % 8, "info"),
            message=match.group("message"),
            raw=raw,
        )

    return SyslogEvent(
        source_host=source_host,
        source_port=source_port,
        facility=None,
        severity="info",
        message=raw,
        raw=raw,
    )


class _SyslogProtocol(asyncio.DatagramProtocol):
    def __init__(self, receiver: "SyslogReceiver") -> None:
        self.receiver = receiver

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.receiver._handle_datagram(data, addr)  # noqa: SLF001


class SyslogReceiver:
    """UDP syslog listener that dispatches parsed events to handlers."""

    def __init__(self, bind_host: str = "0.0.0.0", bind_port: int = 5514) -> None:
        self.bind_host = bind_host
        self.bind_port = bind_port
        self._handlers: list[SyslogHandler] = []
        self._transport: asyncio.DatagramTransport | None = None

    def on_syslog(self, handler: SyslogHandler) -> None:
        self._handlers.append(handler)

    async def start(self) -> None:
        if self._transport is not None:
            return
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _SyslogProtocol(self),
            local_addr=(self.bind_host, self.bind_port),
        )
        self._transport = transport  # type: ignore[assignment]
        logger.info("Syslog receiver listening on {}:{}", self.bind_host, self.bind_port)

    async def stop(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def _handle_datagram(self, data: bytes, addr: tuple[str, int]) -> None:
        event = parse_syslog(data, addr[0], addr[1])
        logger.debug("Syslog received from {} severity={} msg_id={}", event.source_host, event.severity, event.msg_id)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for handler in self._handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    loop.create_task(result)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Syslog handler failed: {}", exc)
