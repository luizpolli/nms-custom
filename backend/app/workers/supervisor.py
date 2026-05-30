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
            asyncio.create_task(self._run_telemetry_receiver_loop(), name="telemetry-receiver"),
            asyncio.create_task(self._run_event_consumer_loop("worker-alarm"), name="worker-alarm"),
            asyncio.create_task(self._run_event_consumer_loop("worker-discovery"), name="worker-discovery"),
            asyncio.create_task(self._run_event_consumer_loop("worker-telemetry"), name="worker-telemetry"),
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

    async def _run_event_consumer_loop(self, kind: str) -> None:
        from app.services.events.consumers import consumer_for_kind

        backoff = 5
        beat = WorkerHeartbeat(kind, 60)
        consumer = consumer_for_kind(kind)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                stats = await consumer.poll_once(count=25, block_ms=1000)
                logger.debug(
                    "{} event consumer pass: seen={} handled={} skipped={} errors={} acked={} claimed={}",
                    kind,
                    stats.seen,
                    stats.handled,
                    stats.skipped,
                    stats.errors,
                    stats.acked,
                    stats.claimed,
                )
                await beat.success()
                if self._stop_event.is_set():
                    break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("{} event consumer error: {}", kind, exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await consumer.close()
        await beat.close()

    async def _run_topology_rebuilder_loop(self) -> None:
        from sqlalchemy import select

        from app.models.device import Device
        from app.services.snmp.engine import SNMPEngine
        from app.services.topology.builder import TopologyBuilder
        from app.services.topology.credentials import build_credentials_map

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
        from app.services.alarms.correlator import AlarmCorrelator
        from app.services.snmp.trap_receiver import SNMPTrapReceiver

        trap_port = int(os.environ.get("TRAP_PORT", "162"))
        backoff = 10
        beat = WorkerHeartbeat("trap-receiver", 60)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                receiver = SNMPTrapReceiver(
                    bind_host=os.environ.get("TRAP_BIND_HOST", "0.0.0.0"),  # nosec B104 - container listener
                    bind_port=trap_port,
                )
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
                    except TimeoutError:
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

    async def _run_telemetry_receiver_loop(self) -> None:
        if not settings.telemetry_receiver_enabled:
            logger.info("Telemetry receiver disabled")
            return
        from app.services.telemetry.receiver import TelemetryReceiver, TelemetryReceiverConfig

        backoff = 10
        beat = WorkerHeartbeat("telemetry-receiver", 60)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                receiver = TelemetryReceiver(
                    async_session_factory,
                    TelemetryReceiverConfig(
                        transport=settings.telemetry_transport,
                        bind_host=settings.telemetry_bind_host,
                        bind_port=settings.telemetry_bind_port,
                    ),
                )
                await beat.success()
                receiver_task = asyncio.create_task(receiver.run(self._stop_event), name="telemetry-receiver-runtime")
                while not self._stop_event.is_set() and not receiver_task.done():
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=30)
                    except TimeoutError:
                        await beat.success()
                if not receiver_task.done():
                    receiver_task.cancel()
                await receiver_task
            except asyncio.CancelledError:
                if "receiver_task" in locals() and not receiver_task.done():
                    receiver_task.cancel()
                break
            except Exception as exc:
                logger.error("Telemetry receiver error: {}", exc)
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
        beat = WorkerHeartbeat("syslog-receiver", 60)
        await beat.starting()
        while not self._stop_event.is_set():
            try:
                receiver = SyslogReceiver(
                    bind_host=settings.syslog_bind_host,
                    bind_port=settings.syslog_bind_port,
                )
                correlator = AlarmCorrelator(async_session_factory)

                async def _handle(event: SyslogEvent) -> None:
                    packet_source_host = event.source_host
                    logical_source_host = event.hostname or event.source_host
                    await correlator.handle_syslog(
                        source_host=logical_source_host,
                        message=event.message,
                        severity=event.severity,
                        category="syslog",
                        facility=event.msg_id or event.app_name or (str(event.facility) if event.facility is not None else None),
                        fields={
                            "raw": event.raw,
                            "packet_source_host": packet_source_host,
                            "hostname": event.hostname or "",
                            "facility": str(event.facility) if event.facility is not None else "",
                            "app_name": event.app_name or "",
                            "msg_id": event.msg_id or "",
                            "structured_data": event.structured_data or "",
                        },
                    )

                receiver.on_syslog(_handle)
                await receiver.start()
                await beat.success()
                # Long-lived receiver: refresh heartbeat periodically so idle
                # syslog periods do not look like receiver failure.
                while not self._stop_event.is_set():
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=30)
                        break
                    except TimeoutError:
                        await beat.success()
                await receiver.stop()
            except asyncio.CancelledError:
                if "receiver" in locals():
                    await receiver.stop()
                break
            except Exception as exc:
                logger.error("Syslog receiver error: {}", exc)
                await beat.failure(str(exc))
                await asyncio.sleep(backoff)
        await beat.close()
