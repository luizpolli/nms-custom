"""Pure scoring/grouping logic shared by the assurance routes."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import (
    CorrelationGroup,
    ImpactedInterface,
    ServiceDependencyImpact,
    ServiceImpact,
    ServiceImpactMember,
)
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.interface import Interface
from app.models.kpi import KPI
from app.models.service import Service, ServiceDependency
from app.services.assurance import clamp_score, severity_penalty

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


def _effective_dependency_direction(dependency: ServiceDependency) -> str:
    override = getattr(dependency, "direction_override", "auto") or "auto"
    if override == "auto":
        return dependency.direction
    return override


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
            effective_direction = _effective_dependency_direction(d)
            if effective_direction == "none":
                continue
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
                    direction_override=getattr(d, "direction_override", "auto") or "auto",
                    effective_direction=effective_direction,
                )
            )
    final_score = clamp_score(service_score - dependency_penalty)

    evidence_payload: dict = {
        "base_score": service_score,
        "dependency_penalty": dependency_penalty,
        "members": [
            {
                "member_id": str(m.member_id),
                "label": m.label,
                "weight": m.weight,
                "score": m.score,
                "active_alarms": m.active_alarms,
                "worst_severity": m.worst_severity,
            }
            for m in members
        ],
        "dependency_impacts": [
            {
                "dependency_id": str(d.dependency_id),
                "target_service_name": d.target_service_name,
                "target_score": d.target_score,
                "weight": d.weight,
                "is_critical": d.is_critical,
                "propagated_penalty": d.propagated_penalty,
                "direction": d.direction,
                "direction_override": d.direction_override,
                "effective_direction": d.effective_direction,
            }
            for d in dependency_impacts
        ],
    }

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
        evidence=evidence_payload,
    )
