"""KPI Engine — orchestrates SNMP polling, mapping, and DB persistence."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, settings as default_settings
from app.models.device import Device
from app.models.kpi import KPI
from app.services.kpi.mapper import (
    InterfaceSnapshot,
    KPIRecord,
    map_cpu_memory,
    map_interfaces,
)
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential


class KPIEngine:
    """Polls SNMP data, maps to KPI records, and persists them."""

    def __init__(
        self,
        snmp_engine: SNMPEngine,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._snmp = snmp_engine
        self._session_factory = session_factory
        self._settings = settings or default_settings
        # In-memory delta store: device_id -> {if_index -> InterfaceSnapshot}
        self._prev_snapshots: dict[uuid.UUID, dict[int, InterfaceSnapshot]] = {}

    async def poll_device(self, device: Device, credential: SNMPCredential) -> list[KPI]:
        """Poll one device, map results to KPI rows, persist, return saved rows."""
        host = device.ip_address
        ts = datetime.now(timezone.utc)
        records: list[KPIRecord] = []

        try:
            cpu_mem = await self._snmp.get_cpu_memory(host, credential)
            records.extend(map_cpu_memory(device.id, cpu_mem, ts))

            interfaces = await self._snmp.get_interfaces(host, credential)
            prev = self._prev_snapshots.get(device.id)
            if_records, new_snap = map_interfaces(device.id, interfaces, ts, prev)
            self._prev_snapshots[device.id] = new_snap
            records.extend(if_records)
        except Exception as exc:  # noqa: BLE001
            logger.error("KPI poll failed for {} ({}): {}", device.name, host, exc)
            return []

        return await self._persist(records)

    async def poll_all(self, devices: list[Device]) -> dict[uuid.UUID, int]:
        """Fan-out poll across all devices, return {device_id: kpi_count}."""
        sem = asyncio.Semaphore(self._settings.poll_workers)
        results: dict[uuid.UUID, int] = {}

        async def _one(dev: Device) -> None:
            async with sem:
                cred = _build_credential(dev, self._settings)
                rows = await self.poll_device(dev, cred)
                results[dev.id] = len(rows)

        await asyncio.gather(*[_one(d) for d in devices], return_exceptions=True)
        return results

    async def aggregate(
        self,
        device_id: uuid.UUID,
        kpi_type: str,
        since: datetime,
        until: datetime,
        bucket: str = "5m",
    ) -> list[dict[str, Any]]:
        """Time-bucket aggregates via date_trunc (Postgres). Returns list of {ts, avg, min, max, count}."""
        pg_interval = _bucket_to_pg(bucket)
        sql = text(
            """
            SELECT
                date_trunc(:interval, timestamp) AS ts,
                AVG(value)   AS avg,
                MIN(value)   AS min,
                MAX(value)   AS max,
                COUNT(*)     AS count
            FROM kpis
            WHERE device_id = :device_id
              AND kpi_type  = :kpi_type
              AND timestamp >= :since
              AND timestamp <  :until
            GROUP BY ts
            ORDER BY ts
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(
                sql,
                {
                    "interval": pg_interval,
                    "device_id": str(device_id),
                    "kpi_type": kpi_type,
                    "since": since,
                    "until": until,
                },
            )
            rows = result.fetchall()

        return [
            {"ts": r.ts, "avg": r.avg, "min": r.min, "max": r.max, "count": r.count}
            for r in rows
        ]

    async def _persist(self, records: list[KPIRecord]) -> list[KPI]:
        """Bulk-insert KPIRecords and evaluate threshold crossings."""
        if not records:
            return []
        kpi_rows = [_record_to_model(r) for r in records]
        async with self._session_factory() as session:
            session.add_all(kpi_rows)
            await session.commit()
            logger.debug("Persisted {} KPI rows", len(kpi_rows))
        await self._evaluate_thresholds(kpi_rows)
        return kpi_rows

    async def _evaluate_thresholds(self, kpi_rows: list[KPI]) -> None:
        from app.services.kpi.thresholds import KPIThresholdEvaluator

        try:
            evaluator = KPIThresholdEvaluator(self._session_factory)
            await evaluator.evaluate(kpi_rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("KPI threshold evaluation failed: {}", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _record_to_model(r: KPIRecord) -> KPI:
    """Convert a KPIRecord dataclass to a KPI ORM instance."""
    return KPI(
        device_id=r.device_id,
        kpi_type=r.kpi_type,
        technology=r.technology,
        value=r.value,
        unit=r.unit,
        kpi_area=r.kpi_area,
        meta=r.metadata,
        timestamp=r.timestamp,
    )


def _build_credential(device: Device, cfg: Settings) -> SNMPCredential:
    """Build an SNMPCredential from device settings (community from config fallback)."""
    return SNMPCredential(
        version=cfg.snmp_version,
        community=cfg.snmp_default_community,
        timeout=float(cfg.poll_timeout),
    )


def _bucket_to_pg(bucket: str) -> str:
    """Convert simplified bucket strings to Postgres date_trunc interval names."""
    _map = {
        "1m": "minute", "5m": "5 minutes", "15m": "15 minutes",
        "1h": "hour", "1d": "day",
    }
    return _map.get(bucket, "5 minutes")
