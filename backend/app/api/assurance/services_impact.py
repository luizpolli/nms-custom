"""Per-service health/impact computation, alerts, and score snapshots."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import ServiceAlert, ServiceImpact
from app.api.assurance.scoring import (
    _compute_service_impact,
    _interface_alarm_match,
    _severity_rank,
)
from app.database import get_db
from app.models.alarm import Alarm
from app.models.interface import Interface
from app.models.service import Service, ServiceScoreSnapshot

router = APIRouter()

_SNAPSHOT_THROTTLE_SECONDS = 60
_DEFAULT_TARGET_SCORE = 90


async def _persist_service_score_snapshots(
    db: AsyncSession,
    impacts: list[ServiceImpact],
    *,
    throttle_seconds: int = _SNAPSHOT_THROTTLE_SECONDS,
) -> None:
    """Persist score snapshots, skipping services with a recent snapshot."""
    if not impacts:
        return

    cutoff = datetime.now(UTC) - timedelta(seconds=throttle_seconds)
    latest_result = await db.execute(
        select(ServiceScoreSnapshot.service_id, func.max(ServiceScoreSnapshot.captured_at))
        .where(ServiceScoreSnapshot.service_id.in_([i.service_id for i in impacts]))
        .group_by(ServiceScoreSnapshot.service_id)
    )
    latest = {row[0]: row[1] for row in latest_result.all()}

    fresh: list[ServiceScoreSnapshot] = []
    for impact in impacts:
        last = latest.get(impact.service_id)
        if last is not None:
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if last >= cutoff:
                continue
        fresh.append(
            ServiceScoreSnapshot(
                service_id=impact.service_id,
                score=impact.score,
                base_score=impact.base_score,
                dependency_penalty=impact.dependency_penalty,
                health_state=impact.health_state,
                evidence=impact.evidence,
            )
        )

    if fresh:
        db.add_all(fresh)
        await db.commit()


@router.get("/services", response_model=list[ServiceImpact])
async def assurance_services(
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[ServiceImpact]:
    """Compute health/impact per registered Service."""
    services_result = await db.execute(select(Service).order_by(Service.name))
    services = list(services_result.scalars().all())
    if not services:
        return []

    alarm_result = await db.execute(
        select(Alarm)
        .where(Alarm.state.in_(["active", "acknowledged", "suppressed"]))
        .order_by(Alarm.last_seen.desc())
        .limit(2000)
    )
    alarms = list(alarm_result.scalars().all())

    interface_result = await db.execute(select(Interface))
    interfaces = list(interface_result.scalars().all())
    interface_oper_status = {i.id: i.oper_status for i in interfaces}

    alarms_by_device: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for a in alarms:
        if a.device_id:
            alarms_by_device[a.device_id].append(a)

    alarms_by_interface: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for iface in interfaces:
        matched = [a for a in alarms if _interface_alarm_match(a, iface)]
        if matched:
            alarms_by_interface[iface.id] = matched

    base_impacts = [
        _compute_service_impact(s, alarms_by_device, alarms_by_interface, interface_oper_status)
        for s in services
    ]
    base_scores = {impact.service_id: impact.score for impact in base_impacts}
    impacts = [
        _compute_service_impact(s, alarms_by_device, alarms_by_interface, interface_oper_status, base_scores)
        for s in services
    ]
    impacts.sort(key=lambda x: (x.score, -_severity_rank(x.worst_severity), x.name))
    await _persist_service_score_snapshots(db, impacts)
    return impacts[:limit]


@router.get("/services/{service_id}", response_model=ServiceImpact)
async def assurance_service_detail(
    service_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceImpact:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    alarm_result = await db.execute(
        select(Alarm).where(Alarm.state.in_(["active", "acknowledged", "suppressed"])).limit(2000)
    )
    alarms = list(alarm_result.scalars().all())

    interface_result = await db.execute(select(Interface))
    interfaces = list(interface_result.scalars().all())
    interface_oper_status = {i.id: i.oper_status for i in interfaces}

    alarms_by_device: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for a in alarms:
        if a.device_id:
            alarms_by_device[a.device_id].append(a)

    alarms_by_interface: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for iface in interfaces:
        matched = [a for a in alarms if _interface_alarm_match(a, iface)]
        if matched:
            alarms_by_interface[iface.id] = matched

    all_services_result = await db.execute(select(Service))
    all_services = list(all_services_result.scalars().all())
    base_scores = {
        s.id: _compute_service_impact(s, alarms_by_device, alarms_by_interface, interface_oper_status).score
        for s in all_services
    }
    return _compute_service_impact(service, alarms_by_device, alarms_by_interface, interface_oper_status, base_scores)


@router.get("/service-alerts", response_model=list[ServiceAlert])
async def assurance_service_alerts(
    db: Annotated[AsyncSession, Depends(get_db)],
    default_target: int = _DEFAULT_TARGET_SCORE,
) -> list[ServiceAlert]:
    """Return services whose current score is below their target threshold."""
    default_target = max(0, min(default_target, 100))
    services_result = await db.execute(select(Service).order_by(Service.name))
    services = list(services_result.scalars().all())
    if not services:
        return []

    alarm_result = await db.execute(
        select(Alarm)
        .where(Alarm.state.in_(["active", "acknowledged", "suppressed"]))
        .order_by(Alarm.last_seen.desc())
        .limit(2000)
    )
    alarms = list(alarm_result.scalars().all())

    interface_result = await db.execute(select(Interface))
    interfaces = list(interface_result.scalars().all())
    interface_oper_status = {i.id: i.oper_status for i in interfaces}

    alarms_by_device: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for a in alarms:
        if a.device_id:
            alarms_by_device[a.device_id].append(a)

    alarms_by_interface: dict[uuid.UUID, list[Alarm]] = defaultdict(list)
    for iface in interfaces:
        matched = [a for a in alarms if _interface_alarm_match(a, iface)]
        if matched:
            alarms_by_interface[iface.id] = matched

    base_impacts = [
        _compute_service_impact(s, alarms_by_device, alarms_by_interface, interface_oper_status)
        for s in services
    ]
    base_scores = {impact.service_id: impact.score for impact in base_impacts}
    impacts = [
        _compute_service_impact(s, alarms_by_device, alarms_by_interface, interface_oper_status, base_scores)
        for s in services
    ]
    target_by_id = {s.id: s.target_score for s in services}

    alerts: list[ServiceAlert] = []
    for impact in impacts:
        target = target_by_id.get(impact.service_id)
        effective_target = target if target is not None else default_target
        if impact.score >= effective_target:
            continue
        alerts.append(
            ServiceAlert(
                service_id=impact.service_id,
                name=impact.name,
                kind=impact.kind,
                score=impact.score,
                target_score=effective_target,
                deficit=effective_target - impact.score,
                health_state=impact.health_state,
                worst_severity=impact.worst_severity,
                impacted_member_count=impact.impacted_member_count,
                active_alarm_count=impact.active_alarm_count,
            )
        )

    alerts.sort(key=lambda a: (-a.deficit, a.name))
    return alerts
