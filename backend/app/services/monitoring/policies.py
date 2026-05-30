"""Monitoring policy presets and execution helpers."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.config import settings as default_settings
from app.models.device import Device
from app.models.kpi import KPI
from app.models.monitoring_policy import MonitoringPolicy
from app.services.kpi.engine import KPIEngine, _build_credential
from app.services.snmp.engine import SNMPEngine
from app.services.workers.sharding import filter_for_shard, normalize_shard_config

POLICY_PRESETS = [
    {
        "name": "Device Health",
        "policy_type": "device_health",
        "interval_seconds": 300,
        "description": "Cisco EPNM default: CPU, memory, environmental temperature and availability every 5 minutes.",
    },
    {
        "name": "Interface Health",
        "policy_type": "interface_health",
        "interval_seconds": 300,
        "description": "Cisco EPNM default: interface status, discards, errors, utilization and byte rates every 5 minutes.",
    },
    {
        "name": "Custom MIB Polling",
        "policy_type": "custom_mib",
        "interval_seconds": 900,
        "description": "Poll unsupported/custom MIB OIDs and make them reportable.",
    },
    {
        "name": "Optical SFP",
        "policy_type": "optical_sfp",
        "interval_seconds": 60,
        "description": "Cisco EPNM default: SFP temperature, voltage, current, TX/RX optical power every 1 minute.",
    },
    {
        "name": "Optical 15 mins",
        "policy_type": "optical_15m",
        "interval_seconds": 900,
        "description": "Optical/OTN collection for 1 hour to 1 week retention windows every 15 minutes.",
    },
    {
        "name": "Optical 1 day",
        "policy_type": "optical_1d",
        "interval_seconds": 86400,
        "description": "Long-duration optical collection for periods above two weeks every 24 hours.",
    },
    {
        "name": "MPLS Link Performance",
        "policy_type": "mpls_link_performance",
        "interval_seconds": 900,
        "description": "Cisco EPNM default: average/min/max delay and RX/TX packets every 15 minutes.",
    },
    {
        "name": "IP SLA",
        "policy_type": "ip_sla",
        "interval_seconds": 900,
        "description": "Cisco EPNM default: real-time IP SLA performance every 15 minutes.",
    },
    {
        "name": "GNSS",
        "policy_type": "gnss",
        "interval_seconds": 3600,
        "description": "GNSS module/antenna/satellite status. Cisco default is 30 minutes; nearest supported slot is 1 hour.",
    },
    {
        "name": "Syslog Monitoring",
        "policy_type": "syslog",
        "interval_seconds": 60,
        "description": "Passive syslog alarm processing; interval controls policy health/report cadence.",
    },
]

DEFAULT_POLICY_SUITE = [
    ("All Devices — 1 minute", "optical_sfp", 60, "High-frequency collection slot for fast-changing interface/optical metrics."),
    ("All Devices — 5 minutes", "device_health", 300, "Default device/interface health cadence for CPU, memory, availability and interface KPIs."),
    ("All Devices — 15 minutes", "custom_mib", 900, "Standard performance/custom MIB report cadence."),
    ("All Devices — 1 hour", "gnss", 3600, "Hourly slower-changing environment/GNSS/status collection."),
    ("All Devices — 6 hours", "custom_mib", 21600, "Six-hour periodic baseline collection."),
    ("All Devices — 12 hours", "custom_mib", 43200, "Twelve-hour periodic baseline collection."),
    ("All Devices — 24 hours", "optical_1d", 86400, "Daily long-retention collection."),
]


class MonitoringPolicyRunner:
    """Executes due monitoring policies for all or selected devices."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        snmp_engine: SNMPEngine | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._sf = session_factory
        self._settings = settings or default_settings
        self._snmp = snmp_engine or SNMPEngine()
        self._kpi_engine = KPIEngine(self._snmp, session_factory, self._settings)

    async def run_due(self) -> int:
        await ensure_default_policy_suite(self._sf)
        now = datetime.now(UTC)
        async with self._sf() as session:
            result = await session.execute(select(MonitoringPolicy).where(MonitoringPolicy.enabled.is_(True)))
            policies = [p for p in result.scalars().all() if _is_due(p, now)]

        concurrency = max(1, int(self._settings.worker_max_concurrency or 1))
        sem = asyncio.Semaphore(concurrency)

        async def _run(policy: MonitoringPolicy) -> None:
            async with sem:
                await self.run_policy(policy.id)

        await asyncio.gather(*[_run(policy) for policy in policies])
        return len(policies)

    async def run_policy(self, policy_id: uuid.UUID) -> dict[str, int]:
        async with self._sf() as session:
            policy = await session.get(MonitoringPolicy, policy_id)
            if policy is None:
                return {}
            devices = await self._target_devices(session, policy)

        started = datetime.now(UTC)
        try:
            counts = await self._execute(policy, devices)
            status = "success"
            error = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Monitoring policy failed: {}", exc)
            counts = {}
            status = "failed"
            error = str(exc)

        async with self._sf() as session:
            policy = await session.get(MonitoringPolicy, policy_id)
            if policy is not None:
                policy.last_run_at = started
                policy.next_run_at = started + timedelta(seconds=policy.interval_seconds)
                policy.last_status = status
                policy.last_error = error
                policy.updated_at = datetime.now(UTC)
                await session.commit()
        return counts

    async def _target_devices(self, session: AsyncSession, policy: MonitoringPolicy) -> list[Device]:
        stmt = select(Device).where(Device.credential_id.is_not(None))
        if not policy.target_all_devices and policy.device_ids:
            stmt = stmt.where(Device.id.in_([uuid.UUID(str(v)) for v in policy.device_ids]))
        result = await session.execute(stmt)
        devices = list(result.scalars().all())
        shard = normalize_shard_config(self._settings.worker_shard_id, self._settings.worker_shard_count)
        return filter_for_shard(devices, shard)  # type: ignore[type-var]  # Device.id is Mapped[UUID], satisfies Shardable at runtime

    async def _execute(self, policy: MonitoringPolicy, devices: list[Device]) -> dict[str, int]:
        if policy.policy_type == "syslog":
            return {str(d.id): 0 for d in devices}
        if policy.policy_type == "custom_mib" and policy.metric_oids:
            return await self._poll_custom_oids(policy, devices)
        return {str(k): v for k, v in (await self._kpi_engine.poll_all(devices)).items()}

    async def _poll_custom_oids(self, policy: MonitoringPolicy, devices: list[Device]) -> dict[str, int]:
        counts: dict[str, int] = {}
        now = datetime.now(UTC)
        async with self._sf() as session:
            for device in devices:
                cred = _build_credential(device, self._settings)
                rows: list[KPI] = []
                for metric in policy.metric_oids:
                    oid = str(metric.get("oid", "")).strip()
                    if not oid:
                        continue
                    result = await self._snmp.poller.get(device.ip_address, [oid], cred)  # noqa: SLF001
                    if not result.success:
                        continue
                    for got_oid, raw_value in result.varbinds.items():
                        try:
                            value = float(raw_value)
                        except ValueError:
                            continue
                        rows.append(
                            KPI(
                                device_id=device.id,
                                kpi_type=str(metric.get("name") or got_oid)[:50],
                                metric_name=str(metric.get("name") or got_oid)[:255],
                                technology=policy.policy_type,
                                value=value,
                                unit=str(metric.get("unit") or "")[:20] or None,
                                kpi_area="custom_mib",
                                source_type="snmp",
                                object_type="device",
                                object_id=str(device.id),
                                quality="good",
                                meta={"policy_id": str(policy.id), "oid": got_oid},
                                labels={"policy": policy.name},
                                timestamp=now,
                            )
                        )
                if rows:
                    session.add_all(rows)
                counts[str(device.id)] = len(rows)
            await session.commit()
        return counts


def _is_due(policy: MonitoringPolicy, now: datetime) -> bool:
    if policy.next_run_at is not None:
        return _as_aware(policy.next_run_at) <= now
    if policy.last_run_at is None:
        return True
    return _as_aware(policy.last_run_at) + timedelta(seconds=policy.interval_seconds) <= now


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def ensure_default_policy_suite(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Create the all-device interval policy suite once, without overwriting user edits."""
    async with session_factory() as session:
        existing = (await session.execute(select(MonitoringPolicy.name))).scalars().all()
        existing_names = set(existing)
        created = False
        for name, policy_type, interval, description in DEFAULT_POLICY_SUITE:
            if name in existing_names:
                continue
            session.add(
                MonitoringPolicy(
                    name=name,
                    description=description,
                    policy_type=policy_type,
                    enabled=True,
                    interval_seconds=interval,
                    target_all_devices=True,
                    device_ids=[],
                    metric_oids=[],
                    thresholds={},
                )
            )
            created = True
        if created:
            await session.commit()
