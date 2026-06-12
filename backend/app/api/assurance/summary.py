"""Network-wide assurance summary."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import AssuranceSummary, ImpactedDevice
from app.api.assurance.scoring import (
    _SEVERITY_ORDER,
    _build_groups,
    _build_impacted_interfaces,
    _device_name,
    _health_state,
    _worst_alarm,
)
from app.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.kpi import KPI
from app.services.assurance import clamp_score, severity_penalty

router = APIRouter()


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

    since = datetime.now(UTC) - timedelta(hours=24)
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
