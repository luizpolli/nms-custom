"""Assurance API — health score, correlation groups, and event timeline."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.kpi import KPI
from app.services.assurance import clamp_score, severity_penalty

router = APIRouter()


class ImpactedDevice(BaseModel):
    device_id: uuid.UUID | None = None
    name: str
    source_host: str | None = None
    score: int
    active_alarms: int
    worst_severity: str
    last_seen: datetime | None = None


class CorrelationGroup(BaseModel):
    group_key: str
    root_alarm_id: uuid.UUID | None = None
    root_cause: str
    severity: str
    category: str
    state: str
    active_count: int
    occurrence_count: int
    impacted_devices: list[str] = Field(default_factory=list)
    first_seen: datetime
    last_seen: datetime


class TimelineEvent(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    severity: str
    source_type: str
    source_host: str
    message: str
    correlation_key: str | None = None
    device_id: uuid.UUID | None = None
    object_type: str | None = None
    object_id: str | None = None


class AssuranceSummary(BaseModel):
    network_score: int
    health_state: str
    active_alarm_count: int
    active_group_count: int
    impacted_device_count: int
    baseline_breach_count: int
    top_impacted_devices: list[ImpactedDevice]
    top_groups: list[CorrelationGroup]


_SEVERITY_ORDER = {"critical": 5, "major": 4, "minor": 3, "warning": 2, "info": 1, "clear": 0}


def _health_state(score: int) -> str:
    if score >= 90:
        return "healthy"
    if score >= 75:
        return "degraded"
    if score >= 50:
        return "impacted"
    return "critical"


def _group_key(alarm: Alarm) -> str:
    if alarm.correlation_group_id:
        return f"group:{alarm.correlation_group_id}"
    return alarm.dedup_key or alarm.correlation_key or f"alarm:{alarm.id}"


def _worst_alarm(alarms: list[Alarm]) -> Alarm:
    return sorted(
        alarms,
        key=lambda a: (_SEVERITY_ORDER.get((a.severity or "info").lower(), 1), a.occurrence_count, a.last_seen),
        reverse=True,
    )[0]


def _build_groups(alarms: list[Alarm], limit: int = 10) -> list[CorrelationGroup]:
    grouped: dict[str, list[Alarm]] = defaultdict(list)
    for alarm in alarms:
        grouped[_group_key(alarm)].append(alarm)

    groups: list[CorrelationGroup] = []
    for key, items in grouped.items():
        root = _worst_alarm(items)
        impacted = sorted({a.source_host for a in items if a.source_host})
        active_items = [a for a in items if a.state == "active"]
        groups.append(
            CorrelationGroup(
                group_key=key,
                root_alarm_id=root.root_alarm_id or root.id,
                root_cause=root.message,
                severity=root.severity,
                category=root.category,
                state="active" if active_items else root.state,
                active_count=len(active_items),
                occurrence_count=sum(a.occurrence_count for a in items),
                impacted_devices=impacted,
                first_seen=min(a.first_seen for a in items),
                last_seen=max(a.last_seen for a in items),
            )
        )
    return sorted(
        groups,
        key=lambda g: (_SEVERITY_ORDER.get(g.severity, 1), g.active_count, g.last_seen),
        reverse=True,
    )[:limit]


def _device_name(device_by_id: dict[uuid.UUID, Device], alarm: Alarm) -> str:
    if alarm.device_id and alarm.device_id in device_by_id:
        return device_by_id[alarm.device_id].name
    return alarm.source_host or "unknown"


@router.get("/summary", response_model=AssuranceSummary)
async def assurance_summary(db: Annotated[AsyncSession, Depends(get_db)]) -> AssuranceSummary:
    alarm_result = await db.execute(
        select(Alarm).where(Alarm.state.in_(["active", "acknowledged"])).order_by(Alarm.last_seen.desc()).limit(500)
    )
    alarms = list(alarm_result.scalars().all())

    device_result = await db.execute(select(Device))
    devices = list(device_result.scalars().all())
    device_by_id = {d.id: d for d in devices}

    penalties_by_device: dict[str, int] = defaultdict(int)
    alarms_by_device: dict[str, list[Alarm]] = defaultdict(list)
    for alarm in alarms:
        key = str(alarm.device_id) if alarm.device_id else alarm.source_host
        penalties_by_device[key] += severity_penalty(alarm.severity, alarm.occurrence_count)
        alarms_by_device[key].append(alarm)

    impacted_devices: list[ImpactedDevice] = []
    for key, items in alarms_by_device.items():
        worst = _worst_alarm(items)
        impacted_devices.append(
            ImpactedDevice(
                device_id=worst.device_id,
                name=_device_name(device_by_id, worst),
                source_host=worst.source_host,
                score=clamp_score(100 - penalties_by_device[key]),
                active_alarms=len([a for a in items if a.state == "active"]),
                worst_severity=worst.severity,
                last_seen=max(a.last_seen for a in items),
            )
        )
    impacted_devices.sort(key=lambda d: (d.score, -_SEVERITY_ORDER.get(d.worst_severity, 1)))

    if devices:
        healthy_device_count = max(0, len(devices) - len(impacted_devices))
        total_score = sum(d.score for d in impacted_devices) + healthy_device_count * 100
        network_score = clamp_score(total_score / len(devices))
    else:
        network_score = clamp_score(100 - sum(severity_penalty(a.severity, a.occurrence_count) for a in alarms))

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    baseline_result = await db.execute(
        select(func.count()).select_from(KPI).where(KPI.quality != "good", KPI.timestamp >= since)
    )
    baseline_breach_count = int(baseline_result.scalar_one() or 0)

    groups = _build_groups(alarms)
    return AssuranceSummary(
        network_score=network_score,
        health_state=_health_state(network_score),
        active_alarm_count=len([a for a in alarms if a.state == "active"]),
        active_group_count=len([g for g in groups if g.state == "active"]),
        impacted_device_count=len(impacted_devices),
        baseline_breach_count=baseline_breach_count,
        top_impacted_devices=impacted_devices[:10],
        top_groups=groups[:10],
    )


@router.get("/groups", response_model=list[CorrelationGroup])
async def assurance_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    state: str = "active",
    limit: int = 50,
) -> list[CorrelationGroup]:
    stmt = select(Alarm)
    if state:
        stmt = stmt.where(Alarm.state == state)
    stmt = stmt.order_by(Alarm.last_seen.desc()).limit(1000)
    result = await db.execute(stmt)
    return _build_groups(list(result.scalars().all()), limit=min(limit, 200))


@router.get("/timeline", response_model=list[TimelineEvent])
async def assurance_timeline(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = None,
    source_host: str | None = None,
    correlation_key: str | None = None,
    limit: int = 100,
) -> list[TimelineEvent]:
    stmt = select(Alarm)
    if device_id:
        stmt = stmt.where(Alarm.device_id == device_id)
    if source_host:
        stmt = stmt.where(Alarm.source_host == source_host)
    if correlation_key:
        stmt = stmt.where(Alarm.correlation_key == correlation_key)
    stmt = stmt.order_by(Alarm.last_seen.desc()).limit(min(limit, 500))
    result = await db.execute(stmt)
    return [
        TimelineEvent(
            id=str(a.id),
            timestamp=a.last_seen,
            event_type=a.event_type,
            severity=a.severity,
            source_type=a.source_type,
            source_host=a.source_host,
            message=a.message,
            correlation_key=a.correlation_key,
            device_id=a.device_id,
            object_type=a.object_type,
            object_id=a.object_id,
        )
        for a in result.scalars().all()
    ]
