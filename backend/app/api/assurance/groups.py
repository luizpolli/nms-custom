"""Correlation group listing, lifecycle actions, and event timeline."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import (
    CorrelationGroup,
    GroupLifecycleRequest,
    GroupLifecycleResponse,
    TimelineEvent,
)
from app.api.assurance.scoring import _build_groups, _group_key
from app.database import get_db
from app.models.alarm import Alarm
from app.models.audit import AuditLog

router = APIRouter()


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
    now = datetime.now(UTC)
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
    now = datetime.now(UTC)
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
