"""Event-driven service score snapshot trigger.

Recompute service impacts and persist snapshots immediately when a major
incident lands, so the score history sparkline and alerts reflect reality
without waiting for the next scheduled ``/api/assurance/services`` poll.

Bypasses the standard 60s throttle used by the periodic write path.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alarm import Alarm
from app.models.interface import Interface
from app.models.service import Service, ServiceScoreSnapshot


# Severities that warrant an immediate snapshot. Lower-severity churn keeps
# riding the 60s throttled path to avoid write amplification.
SNAPSHOT_SEVERITIES: frozenset[str] = frozenset({"critical", "major", "clear"})


async def maybe_snapshot_for_alarm(session: AsyncSession, alarm: Alarm) -> int:
    """Persist a fresh snapshot when ``alarm`` is severe enough to matter.

    Returns the number of snapshots written. Failures are logged and
    swallowed — callers should never have their alarm path break because of
    an opportunistic snapshot.
    """
    severity = (alarm.severity or "").lower()
    if severity not in SNAPSHOT_SEVERITIES:
        return 0
    try:
        return await snapshot_all_services(session)
    except Exception:  # pragma: no cover - defensive
        logger.exception("event-driven service snapshot failed for alarm {}", alarm.id)
        return 0


async def snapshot_all_services(session: AsyncSession) -> int:
    """Compute current scores for every service and write snapshots (no throttle)."""
    from app.api.assurance import (  # local import to avoid circular dependency
        _compute_service_impact,
        _interface_alarm_match,
    )

    services_result = await session.execute(select(Service).order_by(Service.name))
    services = list(services_result.scalars().all())
    if not services:
        return 0

    alarm_result = await session.execute(
        select(Alarm)
        .where(Alarm.state.in_(["active", "acknowledged", "suppressed"]))
        .order_by(Alarm.last_seen.desc())
        .limit(2000)
    )
    alarms = list(alarm_result.scalars().all())

    interface_result = await session.execute(select(Interface))
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

    snapshots = [
        ServiceScoreSnapshot(
            service_id=impact.service_id,
            score=impact.score,
            base_score=impact.base_score,
            dependency_penalty=impact.dependency_penalty,
            health_state=impact.health_state,
            evidence=impact.evidence,
        )
        for impact in impacts
    ]
    session.add_all(snapshots)
    await session.commit()
    return len(snapshots)
