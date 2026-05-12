"""Async SNMP trap receiver — listens on UDP/162 (configurable) and dispatches
incoming traps to a callback for alarm correlation / syslog forwarding.

Use:

    receiver = SNMPTrapReceiver(communities=["public"])
    receiver.on_trap(my_handler)
    await receiver.start()

The handler receives a :class:`TrapEvent` instance.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable

from loguru import logger

try:
    from pysnmp.entity import config, engine
    from pysnmp.carrier.asyncio.dgram import udp
    from pysnmp.entity.rfc3413 import ntfrcv
except ImportError:  # pragma: no cover
    config = engine = udp = ntfrcv = None  # type: ignore[assignment]


TrapHandler = Callable[["TrapEvent"], Awaitable[None] | None]


@dataclass(slots=True)
class TrapEvent:
    """A single received SNMP trap."""

    source_host: str
    source_port: int
    community: str | None
    trap_oid: str | None
    varbinds: dict[str, str] = field(default_factory=dict)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SNMPTrapReceiver:
    """Listens for SNMP traps on a UDP port and dispatches them to handlers."""

    def __init__(
        self,
        bind_host: str = "127.0.0.1",
        bind_port: int = 162,
        communities: list[str] | None = None,
    ) -> None:
        if engine is None:
            raise RuntimeError("pysnmp-lextudio is not installed")
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.communities = communities or ["public"]
        self._engine: object | None = None
        self._handlers: list[TrapHandler] = []
        self._loop_task: asyncio.Task[None] | None = None

    def on_trap(self, handler: TrapHandler) -> None:
        """Register a callback (sync or async) for received traps."""
        self._handlers.append(handler)

    async def start(self) -> None:
        """Bind socket and begin listening. Idempotent."""
        if self._engine is not None:
            return
        snmp_engine = engine.SnmpEngine()

        # Transport
        config.add_transport(
            snmp_engine,
            udp.DOMAIN_NAME + (1,),
            udp.UdpTransport().open_server_mode((self.bind_host, self.bind_port)),
        )

        # Accept any of the configured communities
        for idx, community in enumerate(self.communities, start=1):
            config.add_v1_system(snmp_engine, f"comm-{idx}", community)

        ntfrcv.NotificationReceiver(snmp_engine, self._on_pysnmp_trap)
        self._engine = snmp_engine
        # pysnmp's dispatcher runs in the current event loop after first trap
        snmp_engine.transport_dispatcher.job_started(1)
        logger.info(
            "SNMP trap receiver listening on {}:{}", self.bind_host, self.bind_port
        )

    async def stop(self) -> None:
        if self._engine is None:
            return
        try:
            self._engine.transport_dispatcher.close_dispatcher()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.debug("SNMP trap receiver close ignored: {}", exc)
        self._engine = None

    def _on_pysnmp_trap(
        self,
        snmp_engine: object,
        state_reference: object,
        context_engine_id: object,
        context_name: object,
        var_binds: list,
        cb_ctx: object,
    ) -> None:
        """pysnmp callback — bridge into our async handler list."""
        try:
            transport = snmp_engine.msg_and_pdu_dsp.get_transport_info(state_reference)  # type: ignore[attr-defined]
            host, port = (transport[1] if transport else ("?", 0))
        except Exception:  # noqa: BLE001
            host, port = ("?", 0)

        vb_map: dict[str, str] = {}
        trap_oid: str | None = None
        for oid, value in var_binds:
            oid_s = str(oid)
            val_s = str(value)
            vb_map[oid_s] = val_s
            if oid_s == "1.3.6.1.6.3.1.1.4.1.0":
                trap_oid = val_s

        evt = TrapEvent(
            source_host=str(host),
            source_port=int(port),
            community=None,
            trap_oid=trap_oid,
            varbinds=vb_map,
        )
        logger.debug(
            "Trap received from {}: oid={} varbinds={}", host, trap_oid, len(vb_map)
        )
        # Schedule each handler on the running loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for h in self._handlers:
            try:
                res = h(evt)
                if asyncio.iscoroutine(res):
                    loop.create_task(res)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Trap handler failed: {}", exc)
