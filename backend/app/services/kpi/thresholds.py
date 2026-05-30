"""KPI threshold evaluator — implements Prime Performance Manager-style TCAs.

For each newly inserted KPI sample the evaluator looks up matching thresholds and
raises (or clears) alarms via the regular :class:`AlarmCorrelator` pipeline so that
customer alarm rules, autoclear and dedup behaviour continue to apply.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.kpi import KPI
from app.models.kpi_threshold import KPIThreshold
from app.services.alarms.correlator import AlarmCorrelator

SessionFactory = Callable[[], AsyncSession]

_OPERATORS = {
    "gt": lambda value, target: value > target,
    "gte": lambda value, target: value >= target,
    "lt": lambda value, target: value < target,
    "lte": lambda value, target: value <= target,
}


def _device_key(device: Device | None, kpi: KPI) -> str:
    if device is None:
        return f"device:{kpi.device_id}"
    return device.name or device.ip_address or str(kpi.device_id)


def _matches_device(threshold: KPIThreshold, kpi: KPI) -> bool:
    if threshold.device_id is None:
        return True
    return uuid.UUID(str(threshold.device_id)) == kpi.device_id


def _matches_technology(threshold: KPIThreshold, kpi: KPI) -> bool:
    if not threshold.technology:
        return True
    return (kpi.technology or "") == threshold.technology


def crossed(threshold: KPIThreshold, value: float) -> bool:
    op = _OPERATORS.get(threshold.operator)
    if op is None:
        return False
    return op(value, threshold.value)


def should_clear(threshold: KPIThreshold, value: float) -> bool:
    if not threshold.auto_clear:
        return False
    if threshold.clear_value is None:
        # Without an explicit clear value, treat "not crossed" as the clear condition
        return not crossed(threshold, value)
    if threshold.operator in {"gt", "gte"}:
        return value <= threshold.clear_value
    if threshold.operator in {"lt", "lte"}:
        return value >= threshold.clear_value
    return False


class KPIThresholdEvaluator:
    """Evaluate KPI samples against the configured thresholds."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory
        self._correlator = AlarmCorrelator(session_factory)

    async def evaluate(self, samples: Iterable[KPI]) -> int:
        """Evaluate ``samples`` and emit/clear alarms. Returns number of TCA events."""
        samples = list(samples)
        if not samples:
            return 0

        async with self._sf() as session:
            thresholds = (
                await session.execute(select(KPIThreshold).where(KPIThreshold.enabled.is_(True)))
            ).scalars().all()
            if not thresholds:
                return 0
            device_ids = {s.device_id for s in samples}
            devices = (
                await session.execute(select(Device).where(Device.id.in_(device_ids)))
            ).scalars().all()
            device_map = {d.id: d for d in devices}

        by_type: dict[str, list[KPIThreshold]] = {}
        for t in thresholds:
            by_type.setdefault(t.kpi_type, []).append(t)

        events = 0
        for sample in samples:
            candidates = by_type.get(sample.kpi_type, [])
            for threshold in candidates:
                if not _matches_device(threshold, sample) or not _matches_technology(threshold, sample):
                    continue
                events += await self._emit(threshold, sample, device_map.get(sample.device_id))
        return events

    async def _emit(
        self,
        threshold: KPIThreshold,
        sample: KPI,
        device: Device | None,
    ) -> int:
        host = _device_key(device, sample)
        correlation_key = f"tca:{threshold.id}:{sample.device_id}"
        fields = {
            "kpi_type": sample.kpi_type,
            "value": str(sample.value),
            "unit": sample.unit or "",
            "operator": threshold.operator,
            "threshold": str(threshold.value),
            "threshold_id": str(threshold.id),
            "threshold_name": threshold.name,
            "timestamp": sample.timestamp.isoformat() if sample.timestamp else "",
        }

        if crossed(threshold, sample.value):
            message = (
                f"{threshold.name}: {sample.kpi_type}={sample.value:.2f}{sample.unit or ''} "
                f"{threshold.operator} {threshold.value:.2f} on {host}"
            )
            await self._correlator.handle_event(
                source_host=host,
                event_type=f"tca:{sample.kpi_type}",
                message=message,
                severity=threshold.severity,
                category="performance",
                correlation_key=correlation_key,
                fields=fields,
            )
            return 1

        if should_clear(threshold, sample.value):
            message = (
                f"{threshold.name} cleared: {sample.kpi_type}={sample.value:.2f}{sample.unit or ''} "
                f"on {host}"
            )
            await self._correlator.handle_event(
                source_host=host,
                event_type=f"tca:{sample.kpi_type}",
                message=message,
                severity="clear",
                category="performance",
                correlation_key=correlation_key,
                fields=fields,
            )
            return 1
        return 0


async def evaluate_since(session_factory: SessionFactory, since: datetime) -> int:
    """Helper used by tests/cron to evaluate KPIs newer than ``since``."""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(KPI).where(KPI.timestamp >= since).order_by(KPI.timestamp.asc())
            )
        ).scalars().all()
    if not rows:
        return 0
    evaluator = KPIThresholdEvaluator(session_factory)
    logger.debug("Threshold evaluator: scanning {} KPIs since {}", len(rows), since.isoformat())
    return await evaluator.evaluate(rows)


def now_utc() -> datetime:
    return datetime.now(UTC)
