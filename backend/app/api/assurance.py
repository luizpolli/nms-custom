"""Assurance API — health score, correlation groups, and event timeline."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alarm import Alarm
from app.models.audit import AuditLog
from app.models.device import Device
from app.models.interface import Interface
from app.models.kpi import KPI
from app.models.service import Service, ServiceDependency, ServiceMember, ServiceScoreSnapshot
from app.models.topology import TopologyLink, TopologyNode
from app.services.assurance import clamp_score, severity_penalty
from app.services.assurance.topology_impact import compute_topology_blast_radius

router = APIRouter()


class ImpactedDevice(BaseModel):
    device_id: uuid.UUID | None = None
    name: str
    source_host: str | None = None
    score: int
    active_alarms: int
    worst_severity: str
    last_seen: datetime | None = None


class ImpactedInterface(BaseModel):
    interface_id: uuid.UUID
    device_id: uuid.UUID
    name: str
    score: int
    oper_status: str | None = None
    active_alarms: int = 0
    baseline_breaches: int = 0
    worst_severity: str = "info"


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


class TopologyImpactNode(BaseModel):
    node_id: str
    device_id: uuid.UUID | None = None
    label: str
    depth: int
    role: str | None = None
    via_link_id: uuid.UUID | None = None
    direction: str = "outbound"
    confidence: str = "high"
    reason: str = "directed-link"


class TopologyImpactResponse(BaseModel):
    root: TopologyImpactNode | None = None
    impacted_nodes: list[TopologyImpactNode]
    impacted_count: int
    max_depth: int
    traversal_mode: str = "auto"
    ambiguous_edge_count: int = 0


class GroupLifecycleRequest(BaseModel):
    by_user: str
    reason: str = ""


class GroupLifecycleResponse(BaseModel):
    group_key: str
    state: str
    affected_alarm_count: int


class ServiceImpactMember(BaseModel):
    member_id: uuid.UUID
    device_id: uuid.UUID | None = None
    interface_id: uuid.UUID | None = None
    label: str
    role: str
    weight: float
    score: int
    active_alarms: int
    worst_severity: str


class ServiceDependencyImpact(BaseModel):
    dependency_id: uuid.UUID
    target_service_id: uuid.UUID
    target_service_name: str
    target_score: int
    propagated_penalty: int
    weight: float
    is_critical: bool
    direction: str


class ServiceImpact(BaseModel):
    service_id: uuid.UUID
    name: str
    kind: str
    description: str | None = None
    score: int
    base_score: int | None = None
    dependency_penalty: int = 0
    health_state: str
    member_count: int
    impacted_member_count: int
    active_alarm_count: int
    worst_severity: str
    members: list[ServiceImpactMember] = Field(default_factory=list)
    dependency_impacts: list[ServiceDependencyImpact] = Field(default_factory=list)


class AssuranceSummary(BaseModel):
    network_score: int
    health_state: str
    active_alarm_count: int
    active_group_count: int
    impacted_device_count: int
    impacted_interface_count: int
    baseline_breach_count: int
    top_impacted_devices: list[ImpactedDevice]
    top_impacted_interfaces: list[ImpactedInterface]
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


def _state_for_group(items: list[Alarm]) -> str:
    if any(a.state == "active" for a in items):
        return "active"
    if items and all(a.state == "suppressed" for a in items):
        return "suppressed"
    if any(a.state == "acknowledged" for a in items):
        return "acknowledged"
    return items[0].state if items else "unknown"


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
                state=_state_for_group(items),
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


def _interface_alarm_match(alarm: Alarm, interface: Interface) -> bool:
    object_id = str(alarm.object_id or "")
    corr = str(alarm.correlation_key or "")
    if alarm.object_type == "interface" and object_id in {str(interface.id), interface.name, str(interface.if_index)}:
        return True
    if alarm.device_id and alarm.device_id != interface.device_id:
        return False
    return interface.name in corr or (interface.if_index is not None and f":{interface.if_index}" in corr)


async def _build_impacted_interfaces(db: AsyncSession, alarms: list[Alarm], since: datetime) -> list[ImpactedInterface]:
    interface_result = await db.execute(select(Interface))
    interfaces = list(interface_result.scalars().all())
    if not interfaces:
        return []

    kpi_result = await db.execute(
        select(KPI.object_id, func.count())
        .where(KPI.object_type == "interface", KPI.quality != "good", KPI.timestamp >= since)
        .group_by(KPI.object_id)
    )
    breach_by_object = {str(row[0]): int(row[1]) for row in kpi_result.all() if row[0] is not None}

    impacted: list[ImpactedInterface] = []
    for interface in interfaces:
        matched_alarms = [a for a in alarms if _interface_alarm_match(a, interface)]
        breach_count = breach_by_object.get(str(interface.id), 0) + breach_by_object.get(interface.name, 0)
        if not matched_alarms and not breach_count and interface.oper_status not in {"down", "lowerLayerDown"}:
            continue
        worst = _worst_alarm(matched_alarms) if matched_alarms else None
        penalty = sum(severity_penalty(a.severity, a.occurrence_count) for a in matched_alarms)
        penalty += breach_count * 10
        if interface.oper_status in {"down", "lowerLayerDown"}:
            penalty += 20
        impacted.append(
            ImpactedInterface(
                interface_id=interface.id,
                device_id=interface.device_id,
                name=interface.name,
                score=clamp_score(100 - penalty),
                oper_status=interface.oper_status,
                active_alarms=len([a for a in matched_alarms if a.state == "active"]),
                baseline_breaches=breach_count,
                worst_severity=worst.severity if worst else "warning",
            )
        )
    impacted.sort(key=lambda i: (i.score, -_SEVERITY_ORDER.get(i.worst_severity, 1), i.name))
    return impacted


@router.get("/summary", response_model=AssuranceSummary)
async def assurance_summary(db: Annotated[AsyncSession, Depends(get_db)]) -> AssuranceSummary:
    alarm_result = await db.execute(
        select(Alarm).where(Alarm.state.in_(["active", "acknowledged", "suppressed"])).order_by(Alarm.last_seen.desc()).limit(500)
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
    impacted_interfaces = await _build_impacted_interfaces(db, alarms, since)

    groups = _build_groups(alarms)
    return AssuranceSummary(
        network_score=network_score,
        health_state=_health_state(network_score),
        active_alarm_count=len([a for a in alarms if a.state == "active"]),
        active_group_count=len([g for g in groups if g.state == "active"]),
        impacted_device_count=len(impacted_devices),
        impacted_interface_count=len(impacted_interfaces),
        baseline_breach_count=baseline_breach_count,
        top_impacted_devices=impacted_devices[:10],
        top_impacted_interfaces=impacted_interfaces[:10],
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


async def _alarms_for_group(db: AsyncSession, group_key: str) -> list[Alarm]:
    result = await db.execute(select(Alarm).where(Alarm.state.in_(["active", "acknowledged", "suppressed"])).limit(2000))
    alarms = [alarm for alarm in result.scalars().all() if _group_key(alarm) == group_key]
    if not alarms:
        raise HTTPException(status_code=404, detail="Correlation group not found")
    return alarms


async def _audit_group_action(
    db: AsyncSession,
    *,
    group_key: str,
    actor: str,
    action: str,
    message: str,
    affected_alarm_count: int,
    reason: str = "",
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            object_type="correlation_group",
            object_id=group_key,
            outcome="success",
            message=message,
            details={"group_key": group_key, "affected_alarm_count": affected_alarm_count, "reason": reason},
        )
    )


@router.post("/groups/{group_key}/suppress", response_model=GroupLifecycleResponse)
async def suppress_group(
    group_key: str,
    body: GroupLifecycleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupLifecycleResponse:
    alarms = await _alarms_for_group(db, group_key)
    now = datetime.now(timezone.utc)
    for alarm in alarms:
        raw = dict(alarm.raw_varbinds or {})
        raw["_group_suppression"] = {"by": body.by_user, "reason": body.reason, "suppressed_at": now.isoformat()}
        alarm.raw_varbinds = raw
        alarm.state = "suppressed"
        alarm.ack_by = body.by_user
        alarm.last_seen = now
    await _audit_group_action(
        db,
        group_key=group_key,
        actor=body.by_user,
        action="assurance.group.suppress",
        message=f"Correlation group suppressed by {body.by_user}",
        affected_alarm_count=len(alarms),
        reason=body.reason,
    )
    await db.flush()
    return GroupLifecycleResponse(group_key=group_key, state="suppressed", affected_alarm_count=len(alarms))


@router.post("/groups/{group_key}/unsuppress", response_model=GroupLifecycleResponse)
async def unsuppress_group(
    group_key: str,
    body: GroupLifecycleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GroupLifecycleResponse:
    alarms = await _alarms_for_group(db, group_key)
    now = datetime.now(timezone.utc)
    for alarm in alarms:
        raw = dict(alarm.raw_varbinds or {})
        raw.pop("_group_suppression", None)
        raw.pop("_suppression", None)
        alarm.raw_varbinds = raw or None
        alarm.state = "active"
        alarm.last_seen = now
    await _audit_group_action(
        db,
        group_key=group_key,
        actor=body.by_user,
        action="assurance.group.unsuppress",
        message=f"Correlation group unsuppressed by {body.by_user}",
        affected_alarm_count=len(alarms),
        reason=body.reason,
    )
    await db.flush()
    return GroupLifecycleResponse(group_key=group_key, state="active", affected_alarm_count=len(alarms))


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


def _severity_rank(sev: str | None) -> int:
    return _SEVERITY_ORDER.get((sev or "info").lower(), 1)


def _worst_severity(values: list[str]) -> str:
    if not values:
        return "info"
    return max(values, key=_severity_rank)


def _dependency_penalty(base_score: int, *, weight: float, is_critical: bool) -> int:
    if base_score >= 90:
        return 0
    severity_gap = 100 - base_score
    factor = 0.35 + (0.25 if is_critical else 0.0)
    return min(60, max(1, round(severity_gap * max(weight, 0.0) * factor)))


def _compute_service_impact(
    service: Service,
    alarms_by_device: dict[uuid.UUID, list[Alarm]],
    alarms_by_interface: dict[uuid.UUID, list[Alarm]],
    interface_oper_status: dict[uuid.UUID, str | None],
    dependency_scores: dict[uuid.UUID, int] | None = None,
) -> ServiceImpact:
    members: list[ServiceImpactMember] = []
    severities: list[str] = []
    total_active = 0

    for m in service.members or []:
        label = "unknown"
        member_alarms: list[Alarm] = []
        if m.device_id:
            member_alarms = alarms_by_device.get(m.device_id, [])
            label = m.device.name if m.device else str(m.device_id)
        elif m.interface_id:
            member_alarms = alarms_by_interface.get(m.interface_id, [])
            label = m.interface.name if m.interface else str(m.interface_id)

        penalty = sum(severity_penalty(a.severity, a.occurrence_count) for a in member_alarms)
        if m.interface_id and interface_oper_status.get(m.interface_id) in {"down", "lowerLayerDown"}:
            penalty += 20
        score = clamp_score(100 - penalty)
        active = [a for a in member_alarms if a.state == "active"]
        worst = _worst_severity([a.severity for a in member_alarms])
        if member_alarms:
            severities.append(worst)
        total_active += len(active)
        members.append(
            ServiceImpactMember(
                member_id=m.id,
                device_id=m.device_id,
                interface_id=m.interface_id,
                label=label,
                role=m.role,
                weight=m.weight,
                score=score,
                active_alarms=len(active),
                worst_severity=worst if member_alarms else "info",
            )
        )

    if members:
        total_weight = sum(max(m.weight, 0.0) for m in members) or float(len(members))
        weighted = sum(m.score * max(m.weight, 0.0) for m in members)
        service_score = clamp_score(weighted / total_weight) if total_weight else 100
    else:
        service_score = 100

    impacted_member_count = sum(1 for m in members if m.active_alarms > 0 or m.score < 100)
    dependency_impacts: list[ServiceDependencyImpact] = []
    dependency_penalty = 0
    if dependency_scores:
        for d in service.upstream_dependencies or []:
            target_score = dependency_scores.get(d.target_service_id, 100)
            penalty = _dependency_penalty(target_score, weight=d.weight, is_critical=d.is_critical)
            if penalty <= 0:
                continue
            dependency_penalty += penalty
            dependency_impacts.append(
                ServiceDependencyImpact(
                    dependency_id=d.id,
                    target_service_id=d.target_service_id,
                    target_service_name=d.target_service.name if d.target_service else str(d.target_service_id),
                    target_score=target_score,
                    propagated_penalty=penalty,
                    weight=d.weight,
                    is_critical=d.is_critical,
                    direction=d.direction,
                )
            )
    final_score = clamp_score(service_score - dependency_penalty)

    return ServiceImpact(
        service_id=service.id,
        name=service.name,
        kind=service.kind,
        description=service.description,
        score=final_score,
        base_score=service_score,
        dependency_penalty=dependency_penalty,
        health_state=_health_state(final_score),
        member_count=len(members),
        impacted_member_count=impacted_member_count,
        active_alarm_count=total_active,
        worst_severity=_worst_severity(severities),
        members=sorted(members, key=lambda x: (x.score, -_severity_rank(x.worst_severity))),
        dependency_impacts=sorted(dependency_impacts, key=lambda x: (-x.propagated_penalty, x.target_service_name)),
    )


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


_SNAPSHOT_THROTTLE_SECONDS = 60


async def _persist_service_score_snapshots(
    db: AsyncSession,
    impacts: list[ServiceImpact],
    *,
    throttle_seconds: int = _SNAPSHOT_THROTTLE_SECONDS,
) -> None:
    """Persist score snapshots, skipping services with a recent snapshot."""
    if not impacts:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=throttle_seconds)
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
                last = last.replace(tzinfo=timezone.utc)
            if last >= cutoff:
                continue
        fresh.append(
            ServiceScoreSnapshot(
                service_id=impact.service_id,
                score=impact.score,
                base_score=impact.base_score,
                dependency_penalty=impact.dependency_penalty,
                health_state=impact.health_state,
            )
        )

    if fresh:
        db.add_all(fresh)
        await db.commit()


class ServiceAlert(BaseModel):
    service_id: uuid.UUID
    name: str
    kind: str
    score: int
    target_score: int
    deficit: int
    health_state: str
    worst_severity: str
    impacted_member_count: int
    active_alarm_count: int


_DEFAULT_TARGET_SCORE = 90


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


class ServiceScorePoint(BaseModel):
    captured_at: datetime
    score: int
    base_score: int | None = None
    dependency_penalty: int = 0
    health_state: str


class NetworkScorePoint(BaseModel):
    bucket_start: datetime
    avg_score: float
    min_score: int
    max_score: int
    sample_count: int
    service_count: int


def _bucket_snapshots(
    snapshots: list[ServiceScoreSnapshot],
    since: datetime,
    bucket_minutes: int,
) -> list[NetworkScorePoint]:
    bucket_secs = bucket_minutes * 60
    since_ts = since.timestamp()
    buckets: dict[int, list[tuple[uuid.UUID, int]]] = {}
    for s in snapshots:
        ts = s.captured_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        offset = ts.timestamp() - since_ts
        key = int(offset // bucket_secs)
        buckets.setdefault(key, []).append((s.service_id, s.score))

    result: list[NetworkScorePoint] = []
    for key in sorted(buckets):
        entries = buckets[key]
        scores = [e[1] for e in entries]
        bucket_start = datetime.fromtimestamp(since_ts + key * bucket_secs, tz=timezone.utc)
        result.append(
            NetworkScorePoint(
                bucket_start=bucket_start,
                avg_score=round(sum(scores) / len(scores), 2),
                min_score=int(min(scores)),
                max_score=int(max(scores)),
                sample_count=int(len(scores)),
                service_count=int(len({e[0] for e in entries})),
            )
        )
    return result


@router.get("/history", response_model=list[NetworkScorePoint])
async def assurance_network_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = 24,
    bucket_minutes: int = 15,
) -> list[NetworkScorePoint]:
    hours = max(1, min(hours, 720))
    bucket_minutes = max(1, min(bucket_minutes, 1440))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(ServiceScoreSnapshot)
        .where(ServiceScoreSnapshot.captured_at >= since)
        .order_by(ServiceScoreSnapshot.captured_at.asc())
    )
    snapshots = list(result.scalars().all())
    return _bucket_snapshots(snapshots, since, bucket_minutes)


@router.get("/services/{service_id}/history", response_model=list[ServiceScorePoint])
async def assurance_service_history(
    service_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = 24,
    limit: int = 500,
) -> list[ServiceScorePoint]:
    """Return service score snapshots over the requested time window."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    hours = max(1, min(hours, 24 * 30))
    limit = max(1, min(limit, 5000))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(ServiceScoreSnapshot)
        .where(ServiceScoreSnapshot.service_id == service_id)
        .where(ServiceScoreSnapshot.captured_at >= since)
        .order_by(ServiceScoreSnapshot.captured_at.asc())
        .limit(limit)
    )
    snapshots = list(result.scalars().all())
    return [
        ServiceScorePoint(
            captured_at=s.captured_at,
            score=s.score,
            base_score=s.base_score,
            dependency_penalty=s.dependency_penalty,
            health_state=s.health_state,
        )
        for s in snapshots
    ]


def _node_label(node: TopologyNode) -> str:
    return node.device.name if node.device else node.node_id


def _impact_node(
    node: TopologyNode,
    depth: int,
    *,
    via_link_id: uuid.UUID | None = None,
    direction: str = "outbound",
    confidence: str = "high",
    reason: str = "directed-link",
) -> TopologyImpactNode:
    return TopologyImpactNode(
        node_id=node.node_id,
        device_id=node.device_id,
        label=_node_label(node),
        depth=depth,
        role=node.role,
        via_link_id=via_link_id,
        direction=direction,
        confidence=confidence,
        reason=reason,
    )


@router.get("/impact", response_model=TopologyImpactResponse)
async def topology_impact(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = None,
    node_id: str | None = None,
    max_depth: int = 3,
    traversal_mode: str = "auto",
) -> TopologyImpactResponse:
    """Return role-aware topology blast radius from a root device/node.

    ``auto`` follows directed links and safely explores reverse edges when
    discovery orientation is ambiguous or role hierarchy suggests the persisted
    edge points upstream.
    """
    nodes_result = await db.execute(select(TopologyNode))
    nodes = list(nodes_result.scalars().all())
    if not nodes:
        return TopologyImpactResponse(root=None, impacted_nodes=[], impacted_count=0, max_depth=max_depth, traversal_mode=traversal_mode)

    root = None
    for node in nodes:
        if device_id and node.device_id == device_id:
            root = node
            break
        if node_id and node.node_id == node_id:
            root = node
            break
    if root is None:
        root = nodes[0]

    links_result = await db.execute(select(TopologyLink))
    depth_limit = max(1, min(max_depth, 10))
    graph = compute_topology_blast_radius(
        root=root,
        nodes=nodes,
        links=list(links_result.scalars().all()),
        max_depth=depth_limit,
        traversal_mode=traversal_mode,
    )

    impacted = [
        _impact_node(
            step.node,
            step.depth,
            via_link_id=step.via_link_id,
            direction=step.direction,
            confidence=step.confidence,
            reason=step.reason,
        )
        for step in graph.impacted
    ]
    return TopologyImpactResponse(
        root=_impact_node(root, 0),
        impacted_nodes=impacted,
        impacted_count=len(impacted),
        max_depth=depth_limit,
        traversal_mode=graph.traversal_mode,
        ambiguous_edge_count=graph.ambiguous_edge_count,
    )
