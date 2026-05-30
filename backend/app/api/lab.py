"""Local lab health and simulator visibility routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.kpi import KPI
from app.models.telemetry import TelemetryRawSample
from app.services.events import EventBus
from app.services.observability import get_all_worker_status

router = APIRouter()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _as_utc(value: datetime) -> datetime:
    """Normalize DB timestamps so SQLite/PG timezone behavior does not break comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _histogram_bucket_seconds(window_minutes: int) -> int:
    """Return a compact bucket size for lab EPS histograms."""
    if window_minutes <= 60:
        return 60
    if window_minutes <= 360:
        return 300
    return 3600


def _eps_histogram(timestamps: list[datetime], since: datetime, now: datetime, bucket_seconds: int) -> list[dict[str, Any]]:
    """Build a time-bucketed EPS distribution from already-fetched samples."""
    window_seconds = max((now - since).total_seconds(), 1)
    bucket_count = max(1, int((window_seconds + bucket_seconds - 1) // bucket_seconds))
    counts = [0] * bucket_count

    for timestamp in timestamps:
        timestamp = _as_utc(timestamp)
        if timestamp < since or timestamp > now:
            continue
        index = min(int((timestamp - since).total_seconds() // bucket_seconds), bucket_count - 1)
        counts[index] += 1

    buckets: list[dict[str, Any]] = []
    for index, count in enumerate(counts):
        start = since + timedelta(seconds=index * bucket_seconds)
        end = min(start + timedelta(seconds=bucket_seconds), now)
        seconds = max((end - start).total_seconds(), 1)
        buckets.append(
            {
                "start": _iso(start),
                "end": _iso(end),
                "count": count,
                "eps": round(count / seconds, 2),
            }
        )
    return buckets


def _latency_histogram(values: list[float]) -> dict[str, Any]:
    """Build a fixed latency distribution from KPI latency values in milliseconds."""
    buckets = [
        ("<10ms", None, 10.0),
        ("10-50ms", 10.0, 50.0),
        ("50-100ms", 50.0, 100.0),
        ("100-250ms", 100.0, 250.0),
        ("250ms-1s", 250.0, 1000.0),
        (">=1s", 1000.0, None),
    ]
    rows = []
    for label, lower, upper in buckets:
        count = sum(
            1
            for value in values
            if (lower is None or value >= lower) and (upper is None or value < upper)
        )
        rows.append({"label": label, "lower_ms": lower, "upper_ms": upper, "count": count})
    return {
        "unit": "ms",
        "sample_count": len(values),
        "buckets": rows,
        "note": None if values else "No latency KPI samples in this window; histogram is empty rather than simulated.",
    }


def _scenario_annotation(
    scenario_label: str | None,
    run_id: str | None,
    notes: str | None,
    annotated_at: datetime,
) -> dict[str, Any]:
    """Normalize optional operator labels for exported lab snapshots."""

    def clean(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.strip().split())
        return normalized or None

    label = clean(scenario_label)
    run = clean(run_id)
    text = clean(notes)
    return {
        "scenario_label": label,
        "run_id": run,
        "notes": text,
        "annotated_at": _iso(annotated_at) if any([label, run, text]) else None,
    }


async def _event_bus_summary(since: datetime) -> dict[str, Any]:
    settings = Settings()
    bus = EventBus(redis_url=settings.redis_url, stream_name=settings.event_stream_name)
    try:
        client = await bus._client()  # noqa: SLF001 - diagnostic endpoint
        length = int(await client.xlen(bus.stream_name))
        latest = await client.xrevrange(bus.stream_name, count=200)
        groups_raw = await client.xinfo_groups(bus.stream_name)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc), "stream_length": 0, "recent_count": 0, "groups": []}
    finally:
        await bus.close()

    by_type: dict[str, int] = {}
    by_source: dict[str, int] = {}
    recent_count = 0
    first_recent_id: str | None = None
    last_recent_id: str | None = None
    since_ms = int(since.timestamp() * 1000)
    for stream_id, fields in latest:
        try:
            ts_ms = int(str(stream_id).split("-", 1)[0])
        except ValueError:
            ts_ms = 0
        if ts_ms < since_ms:
            continue
        recent_count += 1
        first_recent_id = str(stream_id)
        last_recent_id = last_recent_id or str(stream_id)
        event_type = str(fields.get("event_type") or "unknown")
        source = str(fields.get("source") or "unknown")
        by_type[event_type] = by_type.get(event_type, 0) + 1
        by_source[source] = by_source.get(source, 0) + 1

    groups = [
        {
            "name": row.get("name"),
            "consumers": int(row.get("consumers") or 0),
            "pending": int(row.get("pending") or 0),
            "last_delivered_id": row.get("last-delivered-id"),
        }
        for row in groups_raw or []
    ]
    return {
        "available": True,
        "stream": bus.stream_name,
        "stream_length": length,
        "recent_count": recent_count,
        "recent_by_type": by_type,
        "recent_by_source": by_source,
        "recent_eps": round(recent_count / max((_now() - since).total_seconds(), 1), 2),
        "first_recent_id": first_recent_id,
        "last_recent_id": last_recent_id,
        "groups": groups,
        "pending_total": sum(group["pending"] for group in groups),
    }


@router.get("/health")
async def lab_health(
    db: Annotated[AsyncSession, Depends(get_db)],
    window_minutes: int = Query(default=15, ge=1, le=1440),
    scenario_label: str | None = Query(default=None, max_length=120),
    run_id: str | None = Query(default=None, max_length=80),
    notes: str | None = Query(default=None, max_length=500),
) -> dict[str, Any]:
    """Return compact local lab visibility for mock traffic and EPS checks."""
    now = _now()
    since = now - timedelta(minutes=window_minutes)

    mock_devices = (
        await db.execute(
            select(Device)
            .where(Device.tags.any("mock"))  # type: ignore[arg-type]  # ARRAY.any(str) valid for Postgres
            .order_by(Device.updated_at.desc().nullslast(), Device.created_at.desc())
            .limit(25)
        )
    ).scalars().all()

    telemetry_row = (
        await db.execute(
            select(
                func.count(TelemetryRawSample.id),
                func.max(TelemetryRawSample.received_at),
                func.count(case((TelemetryRawSample.received_at >= since, 1))),
            )
        )
    ).one()
    kpi_row = (
        await db.execute(
            select(
                func.count(KPI.id),
                func.max(KPI.timestamp),
                func.count(case((KPI.timestamp >= since, 1))),
            ).where(KPI.source_type == "telemetry")
        )
    ).one()
    alarm_rows = (
        await db.execute(
            select(Alarm.source_type, Alarm.state, func.count(Alarm.id))
            .where(Alarm.source_type.in_(["syslog", "snmp_trap", "event"]))
            .group_by(Alarm.source_type, Alarm.state)
        )
    ).all()
    recent_alarm_rows = (
        await db.execute(
            select(Alarm.source_type, func.count(Alarm.id))
            .where(Alarm.last_seen >= since, Alarm.source_type.in_(["syslog", "snmp_trap", "event"]))
            .group_by(Alarm.source_type)
        )
    ).all()
    raw_sample_times = (
        await db.execute(
            select(TelemetryRawSample.received_at)
            .where(TelemetryRawSample.received_at >= since)
            .order_by(TelemetryRawSample.received_at.asc())
            .limit(5000)
        )
    ).scalars().all()
    kpi_times = (
        await db.execute(
            select(KPI.timestamp)
            .where(KPI.source_type == "telemetry", KPI.timestamp >= since)
            .order_by(KPI.timestamp.asc())
            .limit(5000)
        )
    ).scalars().all()
    alarm_times = (
        await db.execute(
            select(Alarm.last_seen)
            .where(Alarm.last_seen >= since, Alarm.source_type.in_(["syslog", "snmp_trap", "event"]))
            .order_by(Alarm.last_seen.asc())
            .limit(5000)
        )
    ).scalars().all()
    latency_values = (
        await db.execute(
            select(KPI.value)
            .where(KPI.kpi_type == "latency", KPI.timestamp >= since)
            .order_by(KPI.timestamp.asc())
            .limit(5000)
        )
    ).scalars().all()

    alarm_summary: dict[str, dict[str, int]] = {}
    for source_type, state, count in alarm_rows:
        alarm_summary.setdefault(source_type, {})[state] = int(count)
    recent_alarm_summary = {source_type: int(count) for source_type, count in recent_alarm_rows}

    workers = await get_all_worker_status()
    event_bus = await _event_bus_summary(since)

    window_seconds = max((now - since).total_seconds(), 1)
    bucket_seconds = _histogram_bucket_seconds(window_minutes)
    return {
        "generated_at": _iso(now),
        "window_minutes": window_minutes,
        "window_start": _iso(since),
        "scenario": _scenario_annotation(scenario_label, run_id, notes, now),
        "mock_devices": [
            {
                "id": str(device.id),
                "name": device.name,
                "ip_address": device.ip_address,
                "status": device.status,
                "platform_family": device.platform_family,
                "updated_at": _iso(device.updated_at),
            }
            for device in mock_devices
        ],
        "telemetry": {
            "raw_samples_total": int(telemetry_row[0] or 0),
            "raw_samples_recent": int(telemetry_row[2] or 0),
            "raw_samples_eps": round(int(telemetry_row[2] or 0) / window_seconds, 2),
            "last_raw_sample_at": _iso(telemetry_row[1]),
            "kpis_total": int(kpi_row[0] or 0),
            "kpis_recent": int(kpi_row[2] or 0),
            "kpis_eps": round(int(kpi_row[2] or 0) / window_seconds, 2),
            "last_kpi_at": _iso(kpi_row[1]),
        },
        "alarms": {
            "by_source_state": alarm_summary,
            "recent_by_source": recent_alarm_summary,
            "recent_eps": round(sum(recent_alarm_summary.values()) / window_seconds, 2),
        },
        "distributions": {
            "bucket_seconds": bucket_seconds,
            "raw_sample_eps": _eps_histogram(list(raw_sample_times), since, now, bucket_seconds),
            "kpi_eps": _eps_histogram(list(kpi_times), since, now, bucket_seconds),
            "alarm_eps": _eps_histogram([ts for ts in alarm_times if ts is not None], since, now, bucket_seconds),
            "latency_ms": _latency_histogram([float(value) for value in latency_values]),
            "truncated_at": 5000,
        },
        "event_bus": event_bus,
        "workers": [worker.to_dict() for worker in workers],
        "summary": {
            "mock_device_count": len(mock_devices),
            "stale_worker_count": sum(1 for worker in workers if worker.is_stale),
            "event_bus_pending": event_bus.get("pending_total", 0),
        },
    }
