"""Local lab health and simulator visibility routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


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
) -> dict[str, Any]:
    """Return compact local lab visibility for mock traffic and EPS checks."""
    now = _now()
    since = now - timedelta(minutes=window_minutes)

    mock_devices = (
        await db.execute(
            select(Device)
            .where(Device.tags.any("mock"))
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

    alarm_summary: dict[str, dict[str, int]] = {}
    for source_type, state, count in alarm_rows:
        alarm_summary.setdefault(source_type, {})[state] = int(count)
    recent_alarm_summary = {source_type: int(count) for source_type, count in recent_alarm_rows}

    workers = await get_all_worker_status()
    event_bus = await _event_bus_summary(since)

    window_seconds = max((now - since).total_seconds(), 1)
    return {
        "generated_at": _iso(now),
        "window_minutes": window_minutes,
        "window_start": _iso(since),
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
        "event_bus": event_bus,
        "workers": [worker.to_dict() for worker in workers],
        "summary": {
            "mock_device_count": len(mock_devices),
            "stale_worker_count": sum(1 for worker in workers if worker.is_stale),
            "event_bus_pending": event_bus.get("pending_total", 0),
        },
    }
