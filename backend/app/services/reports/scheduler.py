"""Report scheduler — runs due :class:`ReportSchedule` rows on a fixed cadence.

The runner is intentionally simple (no cron parser): cadences map to fixed deltas
similar to Prime Performance Manager report schedules, plus a few minute-level slots
for power-users that want frequent automatic exports.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report_schedule import GeneratedReport, ReportSchedule
from app.services.reports.registry import ReportRegistry

SessionFactory = Callable[[], AsyncSession]

CADENCE_SECONDS: dict[str, int] = {
    "every_5m": 300,
    "every_15m": 900,
    "every_1h": 3600,
    "hourly": 3600,
    "every_6h": 21600,
    "every_24h": 86400,
    "daily": 86400,
    "weekly": 86400 * 7,
}


def cadence_delta(cadence: str) -> timedelta:
    seconds = CADENCE_SECONDS.get(cadence)
    if seconds is None:
        raise ValueError(f"Unsupported cadence: {cadence!r}")
    return timedelta(seconds=seconds)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def is_due(schedule: ReportSchedule, now: datetime) -> bool:
    if not schedule.enabled:
        return False
    if schedule.next_run_at is None:
        return True
    return _as_aware(schedule.next_run_at) <= now


def materialize_params(params: dict, now: datetime) -> dict:
    """Resolve relative time parameters before invoking the report.

    Supported sentinels (PPM-inspired):
      - ``since`` / ``until`` may be ISO strings, ``"now"`` or ``"-<n><unit>"`` deltas
        where unit is one of ``m`` (minutes), ``h`` (hours), ``d`` (days), ``w`` (weeks).
    """
    out = dict(params or {})
    for key in ("since", "until"):
        if key not in out:
            continue
        value = out[key]
        if not isinstance(value, str):
            continue
        if value.lower() == "now":
            out[key] = now.isoformat()
            continue
        if value.startswith("-"):
            try:
                magnitude = int(value[1:-1])
                unit = value[-1].lower()
            except ValueError:
                continue
            seconds = {"m": 60, "h": 3600, "d": 86400, "w": 604800}.get(unit)
            if seconds is None:
                continue
            out[key] = (now - timedelta(seconds=magnitude * seconds)).isoformat()
    return out


class ReportScheduleRunner:
    """Runs due report schedules and stores artefacts."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._sf = session_factory
        self._registry = ReportRegistry(session_factory)

    async def run_due(self) -> int:
        now = datetime.now(UTC)
        async with self._sf() as session:
            schedules = (
                await session.execute(
                    select(ReportSchedule).where(ReportSchedule.enabled.is_(True))
                )
            ).scalars().all()
            due = [s for s in schedules if is_due(s, now)]

        for schedule in due:
            await self.run_schedule(schedule.id)
        return len(due)

    async def run_schedule(self, schedule_id: uuid.UUID) -> GeneratedReport | None:
        now = datetime.now(UTC)
        async with self._sf() as session:
            schedule = await session.get(ReportSchedule, schedule_id)
            if schedule is None:
                return None
            params = materialize_params(schedule.params or {}, now)
            try:
                content, filename, content_type = await self._registry.generate(
                    schedule.report_name, params
                )
                status = "ok"
                error: str | None = None
            except Exception as exc:  # noqa: BLE001
                logger.exception("Scheduled report {} failed", schedule.name)
                content = b""
                filename = f"{schedule.report_name}-error.txt"
                content_type = "text/plain"
                status = "failed"
                error = str(exc)

            artefact = GeneratedReport(
                schedule_id=schedule.id,
                report_name=schedule.report_name,
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                content=content,
                status=status,
                error=error,
                generated_at=now,
            )
            session.add(artefact)
            schedule.last_run_at = now
            try:
                schedule.next_run_at = now + cadence_delta(schedule.cadence)
            except ValueError:
                schedule.next_run_at = now + timedelta(days=1)
            schedule.last_status = status
            schedule.last_error = error
            schedule.updated_at = now
            await session.commit()
            await self._prune(session, schedule)
            return artefact

    async def _prune(self, session: AsyncSession, schedule: ReportSchedule) -> None:
        if schedule.retain_last <= 0:
            return
        stmt = (
            select(GeneratedReport.id)
            .where(GeneratedReport.schedule_id == schedule.id)
            .order_by(GeneratedReport.generated_at.desc())
            .offset(schedule.retain_last)
        )
        stale_ids = [row[0] for row in (await session.execute(stmt)).all()]
        if stale_ids:
            await session.execute(delete(GeneratedReport).where(GeneratedReport.id.in_(stale_ids)))
            await session.commit()
