"""WorkerSupervisor — manages background async tasks for NMS Custom."""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from app.config import Settings
from app.database import async_session_factory
from app.services.observability.heartbeat import WorkerHeartbeat

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
            asyncio.create_task(self._run_monitoring_policy_loop(), name="monitoring-policies"),
            asyncio.create_task(self._run_topology_rebuilder_loop(), name="topology-rebuilder"),
            asyncio.create_task(self._run_trap_receiver_loop(), name="trap-receiver"),
            asyncio.create_task(self._run_syslog_receiver_loop(), name="syslog-receiver"),
            asyncio.create_task(self._run_report_scheduler_loop(), name="report-scheduler"),
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

    async def _run_monitoring_policy_loop(self) -> None:
        from app.services.monitoring.policies import MonitoringPolicyRunner

        backoff = 5
        beat = WorkerHeartbeat("monitoring-policies", settings.monitoring_policy_check_interval)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                runner = MonitoringPolicyRunner(async_session_factory)
                due = await runner.run_due()
                logger.debug("Monitoring policy loop complete; {} policies executed", due)
                await beat.success()
                await asyncio.sleep(settings.monitoring_policy_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Monitoring policy loop error: {}", exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await beat.close()

    async def _run_topology_rebuilder_loop(self) -> None:
        from sqlalchemy import select
        from app.models.device import Device
        from app.services.snmp.engine import SNMPEngine
        from app.services.topology.credentials import build_credentials_map
        from app.services.topology.builder import TopologyBuilder

        backoff = 10
        beat = WorkerHeartbeat("topology", settings.topology_poll_interval)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                async with async_session_factory() as session:
                    result = await session.execute(select(Device))
                    devices = result.scalars().all()
                    credentials_map = await build_credentials_map(session, devices, settings)
                snmp = SNMPEngine()
                builder = TopologyBuilder(snmp_engine=snmp, session_factory=async_session_factory)
                await builder.build_full(devices=devices, credentials_map=credentials_map)
                logger.debug("Topology rebuilt for {} devices", len(devices))
                await beat.success()
                await asyncio.sleep(settings.topology_poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Topology rebuilder error: {}", exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await beat.close()

    async def _run_trap_receiver_loop(self) -> None:
        from app.services.snmp.trap_receiver import SNMPTrapReceiver
        from app.services.alarms.correlator import AlarmCorrelator

        trap_port = int(os.environ.get("TRAP_PORT", "162"))
        backoff = 10
        beat = WorkerHeartbeat("trap-receiver", 60)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                receiver = SNMPTrapReceiver(bind_port=trap_port)
                correlator = AlarmCorrelator(async_session_factory)
                receiver.on_trap(correlator.handle_trap)
                await receiver.start()
                await beat.success()
                # Long-lived receiver: refresh heartbeat periodically so the
                # API can distinguish "alive but idle" from "dead/crashed".
                while not self._stop_event.is_set():
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=30)
                        break
                    except asyncio.TimeoutError:
                        await beat.success()
                await receiver.stop()
            except asyncio.CancelledError:
                if "receiver" in locals():
                    await receiver.stop()
                break
            except Exception as exc:
                logger.error("Trap receiver error: {}", exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await beat.close()

    async def _run_report_scheduler_loop(self) -> None:
        from app.services.reports.scheduler import ReportScheduleRunner

        backoff = 30
        beat = WorkerHeartbeat("report-scheduler", settings.report_schedule_check_interval)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                runner = ReportScheduleRunner(async_session_factory)
                ran = await runner.run_due()
                if ran:
                    logger.info("Report scheduler: ran {} scheduled report(s)", ran)
                await beat.success()
                await asyncio.sleep(settings.report_schedule_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Report scheduler error: {}", exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await beat.close()

    async def _run_syslog_receiver_loop(self) -> None:
        if not settings.syslog_enabled:
            logger.info("Syslog receiver disabled")
            return
        from app.services.alarms.correlator import AlarmCorrelator
        from app.services.syslog.receiver import SyslogEvent, SyslogReceiver

        backoff = 10
        while not self._stop_event.is_set():
            try:
                receiver = SyslogReceiver(
                    bind_host=settings.syslog_bind_host,
                    bind_port=settings.syslog_bind_port,
                )
                correlator = AlarmCorrelator(async_session_factory)

                async def _handle(event: SyslogEvent) -> None:
                    await correlator.handle_syslog(
                        source_host=event.source_host,
                        message=event.message,
                        severity=event.severity,
                        category="syslog",
                        facility=event.msg_id or event.app_name or (str(event.facility) if event.facility is not None else None),
                        fields={
                            "raw": event.raw,
                            "facility": str(event.facility) if event.facility is not None else "",
                            "app_name": event.app_name or "",
                            "msg_id": event.msg_id or "",
                            "structured_data": event.structured_data or "",
                        },
                    )

                receiver.on_syslog(_handle)
                await receiver.start()
                await self._stop_event.wait()
                await receiver.stop()
            except asyncio.CancelledError:
                if "receiver" in locals():
                    await receiver.stop()
                break
            except Exception as exc:
                logger.error("Syslog receiver error: {}", exc)
                await asyncio.sleep(backoff)
