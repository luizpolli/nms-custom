"""Performance / KPI API routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.device import Device
from app.models.kpi import KPI
from app.schemas.kpi import KPIAggregate, KPIRead
from app.services.kpi.engine import KPIEngine
from app.services.snmp.engine import SNMPEngine

router = APIRouter()


def _kpi_to_read(kpi: KPI) -> KPIRead:
    return KPIRead(
        id=kpi.id,
        device_id=kpi.device_id,
        kpi_type=kpi.kpi_type,
        metric_name=kpi.metric_name,
        technology=kpi.technology,
        value=kpi.value,
        unit=kpi.unit,
        kpi_area=kpi.kpi_area,
        source_type=kpi.source_type,
        object_type=kpi.object_type,
        object_id=kpi.object_id,
        quality=kpi.quality,
        labels=kpi.labels,
        metadata=kpi.meta,
        timestamp=kpi.timestamp,
    )


@router.get("/devices/{id}/kpis", response_model=list[KPIRead])
async def list_kpis(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    kpi_type: str | None = None,
    object_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(1000, ge=1, le=10000),
) -> list[KPIRead]:
    stmt = select(KPI).where(KPI.device_id == id)
    if kpi_type:
        stmt = stmt.where(KPI.kpi_type == kpi_type)
    if object_id:
        stmt = stmt.where(KPI.object_id == object_id)
    if since:
        stmt = stmt.where(KPI.timestamp >= since)
    if until:
        stmt = stmt.where(KPI.timestamp <= until)
    stmt = stmt.order_by(KPI.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_kpi_to_read(k) for k in result.scalars().all()]


@router.get("/devices/{id}/kpis/series", response_model=list[str])
async def list_kpi_object_ids(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    kpi_type: str = Query(...),
) -> list[str]:
    """Distinct object_id values reported for this device+metric — e.g. the
    set of StarOS servname/vpnname instances a bulkstats counter has data
    for, used to populate a per-instance picker before charting."""
    stmt = (
        select(KPI.object_id)
        .where(KPI.device_id == id, KPI.kpi_type == kpi_type, KPI.object_id.is_not(None))
        .distinct()
        .order_by(KPI.object_id)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


@router.get("/devices/{id}/kpis/aggregate", response_model=KPIAggregate)
async def aggregate_kpis(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    kpi_type: str = Query(...),
    since: datetime = Query(...),
    until: datetime = Query(...),
    bucket: str = Query("5m"),
    object_id: str | None = Query(None),
) -> list[dict[str, object]]:
    """Return time-bucketed KPI aggregates (avg/min/max/count per bucket)."""
    engine = KPIEngine(SNMPEngine(), async_session_factory)
    return await engine.aggregate(device_id=id, kpi_type=kpi_type, since=since, until=until, bucket=bucket, object_id=object_id)  # type: ignore[return-value]


@router.get("/summary")
async def performance_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    # Compute avg CPU and mem across last sample per device
    cpu_stmt = (
        select(func.avg(KPI.value))
        .where(KPI.kpi_type == "cpu_5min")
    )
    mem_stmt = (
        select(func.avg(KPI.value))
        .where(KPI.kpi_type == "mem_used_pct")
    )
    cpu_result = await db.execute(cpu_stmt)
    mem_result = await db.execute(mem_stmt)
    cpu_avg = cpu_result.scalar_one_or_none() or 0.0
    mem_avg = mem_result.scalar_one_or_none() or 0.0

    # Top 10 devices by cpu_5min
    top_stmt = (
        select(KPI.device_id, func.max(KPI.value).label("cpu_5min"))
        .where(KPI.kpi_type == "cpu_5min")
        .group_by(KPI.device_id)
        .order_by(func.max(KPI.value).desc())
        .limit(10)
    )
    top_result = await db.execute(top_stmt)
    top_rows = top_result.all()

    # Fetch device names
    device_ids = [r.device_id for r in top_rows]
    names: dict[uuid.UUID, str] = {}
    if device_ids:
        dev_result = await db.execute(select(Device).where(Device.id.in_(device_ids)))
        for d in dev_result.scalars().all():
            names[d.id] = d.name

    top_devices = [
        {"device_id": str(r.device_id), "name": names.get(r.device_id, ""), "cpu_5min": r.cpu_5min}
        for r in top_rows
    ]
    return {"cpu_avg": cpu_avg, "mem_avg": mem_avg, "top_devices": top_devices}
