"""WorkerSupervisor — manages background async tasks for NMS Custom."""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from app.config import Settings
from app.database import async_session_factory

settings = Settings()


class WorkerSupervisor:
    """Manages KPI poller, topology rebuilder, and SNMP trap receiver tasks."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Spawn all background worker tasks."""
        self._stop_event.clear()
        self._tasks = [
            asyncio.create_task(self._run_kpi_poller_loop(), name="kpi-poller"),
            asyncio.create_task(self._run_topology_rebuilder_loop(), name="topology-rebuilder"),
            asyncio.create_task(self._run_trap_receiver_loop(), name="trap-receiver"),
        ]
        logger.info("WorkerSupervisor started {} tasks", len(self._tasks))

    async def stop(self) -> None:
        """Cancel all background tasks gracefully."""
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("WorkerSupervisor stopped")

    async def _run_kpi_poller_loop(self) -> None:
        from sqlalchemy import select
        from app.models.device import Device
        from app.services.kpi.engine import KPIEngine
        from app.services.snmp.engine import SNMPEngine

        backoff = 5
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(Device).where(Device.credential_id != None)  # noqa: E711
                    )
                    devices = result.scalars().all()
                engine = KPIEngine(SNMPEngine(), async_session_factory)
                await engine.poll_all(devices)
                logger.debug("KPI poll complete for {} devices", len(devices))
                await asyncio.sleep(settings.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("KPI poller error: {}", exc)
                await asyncio.sleep(backoff)

    async def _run_topology_rebuilder_loop(self) -> None:
        from sqlalchemy import select
        from app.models.device import Device
        from app.services.snmp.engine import SNMPEngine
        from app.services.topology.builder import TopologyBuilder

        backoff = 10
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as session:
                    result = await session.execute(select(Device))
                    devices = result.scalars().all()
                snmp = SNMPEngine()
                builder = TopologyBuilder(snmp_engine=snmp, session_factory=async_session_factory)
                await builder.build_full(devices=devices)
                logger.debug("Topology rebuilt for {} devices", len(devices))
                await asyncio.sleep(settings.topology_poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Topology rebuilder error: {}", exc)
                await asyncio.sleep(backoff)

    async def _run_trap_receiver_loop(self) -> None:
        from app.services.snmp.trap_receiver import SNMPTrapReceiver
        from app.services.alarms.correlator import AlarmCorrelator

        trap_port = int(os.environ.get("TRAP_PORT", "162"))
        backoff = 10
        while not self._stop_event.is_set():
            try:
                receiver = SNMPTrapReceiver(bind_port=trap_port)
                correlator = AlarmCorrelator(async_session_factory)
                receiver.on_trap(correlator.handle_trap)
                await receiver.start()
                await self._stop_event.wait()
                await receiver.stop()
            except asyncio.CancelledError:
                if "receiver" in locals():
                    await receiver.stop()
                break
            except Exception as exc:
                logger.error("Trap receiver error: {}", exc)
                await asyncio.sleep(backoff)
