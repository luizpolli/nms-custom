"""Dashboard API — aggregated KPI trends, interface utilization, alarm trends, and executive summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.kpi import KPI

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TrendPoint(BaseModel):
    ts: str  # ISO-8601 bucket timestamp
    cpu_avg: float | None = None
    mem_avg: float | None = None
    intf_avg: float | None = None


class DeviceTrendSeries(BaseModel):
    device_id: str
    device_name: str
    points: list[TrendPoint]


class TrendsResponse(BaseModel):
    hours: int
    buckets: int
    series: list[DeviceTrendSeries]


class InterfaceUtilItem(BaseModel):
    device_id: str
    device_name: str
    interface: str
    utilization: float  # percentage 0-100
    direction: str  # "in" | "out" | "combined"


class InterfaceUtilResponse(BaseModel):
    items: list[InterfaceUtilItem]


class AlarmBucket(BaseModel):
    ts: str  # ISO-8601 bucket start
    raised: int
    cleared: int


class AlarmTrendResponse(BaseModel):
    hours: int
    buckets: int
    data: list[AlarmBucket]


class DailyStat(BaseModel):
    label: str
    value: float | int | str
    unit: str | None = None
    delta: float | None = None  # positive = improvement


class TopOffender(BaseModel):
    device_id: str
    device_name: str
    alarm_count: int
    cpu_avg: float | None = None


class ExecutiveSummaryResponse(BaseModel):
    generated_at: str
    uptime_pct: float
    alarms_new_24h: int
    alarms_resolved_24h: int
    mttr_minutes: float | None  # mean time to resolve in minutes
    top_offenders: list[TopOffender]
    kpi_sparklines: dict[str, list[float]]  # e.g. {"cpu": [...7 daily avg values...]}
    daily_stats: list[DailyStat]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _bucket_start(ts: datetime, bucket_seconds: int) -> datetime:
    epoch = ts.timestamp()
    snapped = (int(epoch) // bucket_seconds) * bucket_seconds
    return datetime.fromtimestamp(snapped, tz=UTC)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/trends", response_model=TrendsResponse)
async def get_dashboard_trends(
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = Query(24, ge=1, le=168),
    top_n: int = Query(5, ge=1, le=20),
    buckets: int = Query(24, ge=4, le=48),
) -> TrendsResponse:
    """Return time-bucketed KPI averages for the top-N devices by recent CPU."""
    now = _now_utc()
    since = now - timedelta(hours=hours)
    bucket_seconds = (hours * 3600) // buckets

    # Find top-N devices by avg CPU in the window
    top_stmt = (
        select(KPI.device_id, func.avg(KPI.value).label("avg_cpu"))
        .where(KPI.kpi_type == "cpu", KPI.timestamp >= since)
        .group_by(KPI.device_id)
        .order_by(func.avg(KPI.value).desc())
        .limit(top_n)
    )
    top_result = await db.execute(top_stmt)
    top_rows = top_result.fetchall()
    if not top_rows:
        return TrendsResponse(hours=hours, buckets=buckets, series=[])

    device_ids = [r.device_id for r in top_rows]

    # Load device names
    dev_stmt = select(Device.id, Device.name).where(Device.id.in_(device_ids))
    dev_result = await db.execute(dev_stmt)
    dev_names: dict[str, str] = {str(r.id): r.name for r in dev_result.fetchall()}

    # Fetch all relevant KPI rows for those devices in the window
    kpi_stmt = (
        select(KPI.device_id, KPI.kpi_type, KPI.value, KPI.timestamp)
        .where(KPI.device_id.in_(device_ids), KPI.timestamp >= since)
        .order_by(KPI.timestamp)
    )
    kpi_result = await db.execute(kpi_stmt)
    kpi_rows = kpi_result.fetchall()

    # Build bucket structure per device
    # buckets indexed by (device_id, bucket_index)
    bucket_map: dict[str, dict[int, dict[str, list[float]]]] = {}
    for dev_id in device_ids:
        bucket_map[str(dev_id)] = {i: {"cpu": [], "memory": [], "interface": []} for i in range(buckets)}

    for row in kpi_rows:
        dev_str = str(row.device_id)
        if dev_str not in bucket_map:
            continue
        elapsed = (row.timestamp.replace(tzinfo=UTC) - since).total_seconds()
        idx = min(int(elapsed // bucket_seconds), buckets - 1)
        if idx < 0:
            continue
        ktype = row.kpi_type
        if ktype == "cpu":
            bucket_map[dev_str][idx]["cpu"].append(row.value)
        elif ktype == "memory":
            bucket_map[dev_str][idx]["memory"].append(row.value)
        elif ktype in ("interface_in", "interface_out", "interface_util"):
            bucket_map[dev_str][idx]["interface"].append(row.value)

    series: list[DeviceTrendSeries] = []
    for dev_id in device_ids:
        dev_str = str(dev_id)
        points: list[TrendPoint] = []
        for i in range(buckets):
            bucket_ts = since + timedelta(seconds=i * bucket_seconds)
            bdata = bucket_map[dev_str][i]
            points.append(
                TrendPoint(
                    ts=bucket_ts.isoformat(),
                    cpu_avg=round(sum(bdata["cpu"]) / len(bdata["cpu"]), 2) if bdata["cpu"] else None,
                    mem_avg=round(sum(bdata["memory"]) / len(bdata["memory"]), 2) if bdata["memory"] else None,
                    intf_avg=round(sum(bdata["interface"]) / len(bdata["interface"]), 2) if bdata["interface"] else None,
                )
            )
        series.append(
            DeviceTrendSeries(
                device_id=dev_str,
                device_name=dev_names.get(dev_str, dev_str),
                points=points,
            )
        )

    return TrendsResponse(hours=hours, buckets=buckets, series=series)


@router.get("/interface-utilization", response_model=InterfaceUtilResponse)
async def get_interface_utilization(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(10, ge=1, le=50),
    hours: int = Query(1, ge=1, le=24),
) -> InterfaceUtilResponse:
    """Return top-N most utilized interfaces from recent KPI data."""
    now = _now_utc()
    since = now - timedelta(hours=hours)

    stmt = (
        select(
            KPI.device_id,
            KPI.object_id,
            KPI.kpi_type,
            func.avg(KPI.value).label("avg_val"),
        )
        .where(
            KPI.kpi_type.in_(["interface_in", "interface_out", "interface_util"]),
            KPI.timestamp >= since,
            KPI.object_id.isnot(None),
        )
        .group_by(KPI.device_id, KPI.object_id, KPI.kpi_type)
        .order_by(func.avg(KPI.value).desc())
        .limit(limit * 3)  # over-fetch to merge in/out
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    # Merge by (device_id, object_id)
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = (str(row.device_id), row.object_id)
        if key not in merged:
            merged[key] = {"in": None, "out": None, "combined": None}
        if row.kpi_type == "interface_in":
            merged[key]["in"] = row.avg_val
        elif row.kpi_type == "interface_out":
            merged[key]["out"] = row.avg_val
        elif row.kpi_type == "interface_util":
            merged[key]["combined"] = row.avg_val

    # Compute effective utilization
    items_raw: list[tuple[float, str, str, str, str]] = []
    for (dev_id, obj_id), vals in merged.items():
        if vals["combined"] is not None:
            util = vals["combined"]
            direction = "combined"
        elif vals["in"] is not None and vals["out"] is not None:
            util = max(vals["in"], vals["out"])
            direction = "out" if vals["out"] >= vals["in"] else "in"
        elif vals["in"] is not None:
            util = vals["in"]
            direction = "in"
        elif vals["out"] is not None:
            util = vals["out"]
            direction = "out"
        else:
            continue
        items_raw.append((util, dev_id, obj_id or "unknown", direction, dev_id))

    items_raw.sort(reverse=True)
    items_raw = items_raw[:limit]

    # Load device names
    dev_ids = list({r[1] for r in items_raw})
    if dev_ids:
        dev_stmt = select(Device.id, Device.name).where(
            Device.id.in_([d for d in dev_ids])  # type: ignore[arg-type]
        )
        dev_result = await db.execute(dev_stmt)
        dev_names: dict[str, str] = {str(r.id): r.name for r in dev_result.fetchall()}
    else:
        dev_names = {}

    items: list[InterfaceUtilItem] = [
        InterfaceUtilItem(
            device_id=dev_id,
            device_name=dev_names.get(dev_id, dev_id),
            interface=obj_id,
            utilization=round(min(util, 100.0), 2),
            direction=direction,
        )
        for util, dev_id, obj_id, direction, _ in items_raw
    ]

    return InterfaceUtilResponse(items=items)


@router.get("/alarm-trend", response_model=AlarmTrendResponse)
async def get_alarm_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = Query(24, ge=1, le=168),
    buckets: int = Query(24, ge=4, le=48),
) -> AlarmTrendResponse:
    """Return per-bucket counts of alarms raised and cleared over a time window."""
    now = _now_utc()
    since = now - timedelta(hours=hours)
    bucket_seconds = (hours * 3600) // buckets

    # Raised alarms
    raised_stmt = (
        select(Alarm.first_seen)
        .where(Alarm.first_seen >= since)
    )
    raised_result = await db.execute(raised_stmt)
    raised_rows = raised_result.fetchall()

    # Cleared alarms
    cleared_stmt = (
        select(Alarm.cleared_at)
        .where(Alarm.cleared_at >= since, Alarm.cleared_at.isnot(None))
    )
    cleared_result = await db.execute(cleared_stmt)
    cleared_rows = cleared_result.fetchall()

    raised_counts = [0] * buckets
    cleared_counts = [0] * buckets

    for row in raised_rows:
        ts = row.first_seen
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        elapsed = (ts - since).total_seconds()
        idx = min(int(elapsed // bucket_seconds), buckets - 1)
        if 0 <= idx < buckets:
            raised_counts[idx] += 1

    for row in cleared_rows:  # type: ignore[assignment]
        cleared_ts: datetime | None = row.cleared_at  # type: ignore[assignment]
        if cleared_ts is None:
            continue
        if cleared_ts.tzinfo is None:
            cleared_ts = cleared_ts.replace(tzinfo=UTC)
        elapsed = (cleared_ts - since).total_seconds()
        idx = min(int(elapsed // bucket_seconds), buckets - 1)
        if 0 <= idx < buckets:
            cleared_counts[idx] += 1

    data: list[AlarmBucket] = [
        AlarmBucket(
            ts=(since + timedelta(seconds=i * bucket_seconds)).isoformat(),
            raised=raised_counts[i],
            cleared=cleared_counts[i],
        )
        for i in range(buckets)
    ]

    return AlarmTrendResponse(hours=hours, buckets=buckets, data=data)


@router.get("/executive-summary", response_model=ExecutiveSummaryResponse)
async def get_executive_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExecutiveSummaryResponse:
    """Aggregated executive-level daily KPIs."""
    now = _now_utc()
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    # Device uptime estimate: reachable / total
    dev_stmt = select(Device.status)
    dev_result = await db.execute(dev_stmt)
    all_statuses = [r.status for r in dev_result.fetchall()]
    total_devices = len(all_statuses)
    reachable = sum(1 for s in all_statuses if s == "reachable")
    uptime_pct = round((reachable / total_devices * 100) if total_devices > 0 else 100.0, 2)

    # Alarms new in last 24h
    new_stmt = select(func.count()).select_from(Alarm).where(Alarm.first_seen >= since_24h)
    new_result = await db.execute(new_stmt)
    alarms_new_24h: int = new_result.scalar_one() or 0

    # Alarms resolved in last 24h
    resolved_stmt = (
        select(func.count())
        .select_from(Alarm)
        .where(Alarm.cleared_at >= since_24h, Alarm.cleared_at.isnot(None))
    )
    resolved_result = await db.execute(resolved_stmt)
    alarms_resolved_24h: int = resolved_result.scalar_one() or 0

    # MTTR: avg (cleared_at - first_seen) for alarms cleared in last 7 days
    mttr_stmt = (
        select(Alarm.first_seen, Alarm.cleared_at)
        .where(Alarm.cleared_at >= since_7d, Alarm.cleared_at.isnot(None))
        .limit(500)
    )
    mttr_result = await db.execute(mttr_stmt)
    mttr_rows = mttr_result.fetchall()
    mttr_minutes: float | None = None
    if mttr_rows:
        durations: list[float] = []
        for row in mttr_rows:
            first = row.first_seen
            cleared = row.cleared_at
            if first and cleared:
                if first.tzinfo is None:
                    first = first.replace(tzinfo=UTC)
                if cleared.tzinfo is None:
                    cleared = cleared.replace(tzinfo=UTC)
                diff = (cleared - first).total_seconds() / 60.0
                if diff > 0:
                    durations.append(diff)
        if durations:
            mttr_minutes = round(sum(durations) / len(durations), 1)

    # Top offenders: devices with most alarms in last 24h
    offender_stmt = (
        select(Alarm.device_id, func.count().label("cnt"))
        .where(Alarm.first_seen >= since_24h, Alarm.device_id.isnot(None))
        .group_by(Alarm.device_id)
        .order_by(func.count().desc())
        .limit(5)
    )
    offender_result = await db.execute(offender_stmt)
    offender_rows = offender_result.fetchall()

    offender_dev_ids = [r.device_id for r in offender_rows]
    offender_names: dict[str, str] = {}
    offender_cpu: dict[str, float] = {}
    if offender_dev_ids:
        on_stmt = select(Device.id, Device.name).where(Device.id.in_(offender_dev_ids))
        on_result = await db.execute(on_stmt)
        offender_names = {str(r.id): r.name for r in on_result.fetchall()}

        cpu_stmt = (
            select(KPI.device_id, func.avg(KPI.value).label("avg_cpu"))
            .where(KPI.device_id.in_(offender_dev_ids), KPI.kpi_type == "cpu", KPI.timestamp >= since_24h)
            .group_by(KPI.device_id)
        )
        cpu_result = await db.execute(cpu_stmt)
        offender_cpu = {str(r.device_id): round(r.avg_cpu, 1) for r in cpu_result.fetchall()}

    top_offenders: list[TopOffender] = [
        TopOffender(
            device_id=str(r.device_id),
            device_name=offender_names.get(str(r.device_id), str(r.device_id)),
            alarm_count=r.cnt,
            cpu_avg=offender_cpu.get(str(r.device_id)),
        )
        for r in offender_rows
    ]

    # 7-day daily CPU sparkline
    cpu_sparkline: list[float] = []
    for day_offset in range(6, -1, -1):
        day_start = now - timedelta(days=day_offset + 1)
        day_end = now - timedelta(days=day_offset)
        day_stmt = (
            select(func.avg(KPI.value))
            .where(KPI.kpi_type == "cpu", KPI.timestamp >= day_start, KPI.timestamp < day_end)
        )
        day_result = await db.execute(day_stmt)
        val = day_result.scalar_one()
        cpu_sparkline.append(round(val, 1) if val is not None else 0.0)

    # 7-day alarm count sparkline
    alarm_sparkline: list[float] = []
    for day_offset in range(6, -1, -1):
        day_start = now - timedelta(days=day_offset + 1)
        day_end = now - timedelta(days=day_offset)
        day_stmt = (
            select(func.count())
            .select_from(Alarm)
            .where(Alarm.first_seen >= day_start, Alarm.first_seen < day_end)
        )
        day_result = await db.execute(day_stmt)
        val = day_result.scalar_one()
        alarm_sparkline.append(float(val or 0))

    daily_stats: list[DailyStat] = [
        DailyStat(label="Devices Online", value=reachable, unit=f"/ {total_devices}"),
        DailyStat(label="Alarms (24h)", value=alarms_new_24h),
        DailyStat(label="Resolved (24h)", value=alarms_resolved_24h),
        DailyStat(
            label="MTTR",
            value=f"{mttr_minutes:.0f}" if mttr_minutes is not None else "N/A",
            unit="min" if mttr_minutes is not None else None,
        ),
        DailyStat(label="Network Uptime", value=uptime_pct, unit="%"),
    ]

    return ExecutiveSummaryResponse(
        generated_at=now.isoformat(),
        uptime_pct=uptime_pct,
        alarms_new_24h=alarms_new_24h,
        alarms_resolved_24h=alarms_resolved_24h,
        mttr_minutes=mttr_minutes,
        top_offenders=top_offenders,
        kpi_sparklines={"cpu": cpu_sparkline, "alarms": alarm_sparkline},
        daily_stats=daily_stats,
    )
