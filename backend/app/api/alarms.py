"""Alarms API routes — REST + WebSocket."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.alarm import Alarm
from app.models.alarm_filter import SavedAlarmFilter
from app.models.audit import AuditLog
from app.security.auth import Principal, require_api_auth
from app.services.alarms.correlator import AlarmCorrelator

router = APIRouter()

# Module-level WebSocket registry
_ws_clients: set[WebSocket] = set()


class AlarmRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    device_id: uuid.UUID | None = None
    source_host: str
    severity: str
    category: str
    event_type: str
    message: str
    trap_oid: str | None = None
    correlation_key: str
    state: str
    first_seen: datetime
    last_seen: datetime
    cleared_at: datetime | None = None
    ack_by: str | None = None
    occurrence_count: int
    raw_varbinds: dict | None = None


class AlarmAck(BaseModel):
    by_user: str


class AlarmSuppress(BaseModel):
    by_user: str
    reason: str = ""


class AlarmEventIngest(BaseModel):
    source_type: Literal["syslog", "event"] = "event"
    source_host: str
    event_type: str | None = None
    message: str
    severity: str = "info"
    category: str | None = None
    correlation_key: str | None = None
    facility: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


class AlarmSummary(BaseModel):
    total: int
    active: int
    cleared: int
    acknowledged: int
    critical: int
    major: int
    minor: int
    warning: int


class SavedFilterCreate(BaseModel):
    name: str = Field(..., max_length=128)
    is_public: bool = False
    filters: dict = Field(default_factory=dict)


class SavedFilterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    is_public: bool | None = None
    filters: dict | None = None


class SavedFilterRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    owner: str
    is_public: bool
    filters: dict
    created_at: datetime
    updated_at: datetime


async def _get_or_404(db: AsyncSession, alarm_id: uuid.UUID) -> Alarm:
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm


async def _audit_alarm_action(
    db: AsyncSession,
    *,
    alarm: Alarm,
    actor: str | None,
    action: str,
    message: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor=actor,
            action=action,
            object_type="alarm",
            object_id=str(alarm.id),
            outcome="success",
            message=message,
            details={"alarm_id": str(alarm.id), "correlation_key": alarm.correlation_key, **(details or {})},
        )
    )


@router.get("", response_model=list[AlarmRead])
async def list_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: Optional[uuid.UUID] = None,
    severity: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    event_type: Optional[str] = None,
    source_host: Optional[str] = None,
    q: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AlarmRead]:
    stmt = select(Alarm)
    if device_id:
        stmt = stmt.where(Alarm.device_id == device_id)
    if severity:
        stmt = stmt.where(Alarm.severity == severity)
    if state:
        stmt = stmt.where(Alarm.state == state)
    if category:
        stmt = stmt.where(Alarm.category == category)
    if event_type:
        stmt = stmt.where(Alarm.event_type == event_type)
    if source_host:
        stmt = stmt.where(Alarm.source_host == source_host)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Alarm.message.ilike(pattern),
                Alarm.source_host.ilike(pattern),
                Alarm.event_type.ilike(pattern),
                Alarm.category.ilike(pattern),
                Alarm.correlation_key.ilike(pattern),
            )
        )
    if since:
        stmt = stmt.where(Alarm.first_seen >= since)
    if until:
        stmt = stmt.where(Alarm.first_seen <= until)
    stmt = stmt.order_by(Alarm.last_seen.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return [AlarmRead.model_validate(a) for a in result.scalars().all()]


@router.get("/summary", response_model=AlarmSummary)
async def alarm_summary(db: Annotated[AsyncSession, Depends(get_db)]) -> AlarmSummary:
    total_r = await db.execute(select(func.count()).select_from(Alarm))
    total = total_r.scalar_one()

    async def _count(where) -> int:
        r = await db.execute(select(func.count()).select_from(Alarm).where(where))
        return r.scalar_one()

    active = await _count(Alarm.state == "active")
    cleared = await _count(Alarm.state == "cleared")
    acknowledged = await _count(Alarm.state == "acknowledged")
    critical = await _count(Alarm.severity == "critical")
    major = await _count(Alarm.severity == "major")
    minor = await _count(Alarm.severity == "minor")
    warning = await _count(Alarm.severity == "warning")
    return AlarmSummary(
        total=total, active=active, cleared=cleared, acknowledged=acknowledged,
        critical=critical, major=major, minor=minor, warning=warning,
    )


@router.post("/ingest", response_model=AlarmRead | None, status_code=status.HTTP_202_ACCEPTED)
async def ingest_alarm_event(body: AlarmEventIngest) -> AlarmRead | None:
    """Ingest a syslog or custom event and apply customer alarm rules."""
    correlator = AlarmCorrelator(async_session_factory)
    if body.source_type == "syslog":
        alarm = await correlator.handle_syslog(
            source_host=body.source_host,
            message=body.message,
            severity=body.severity,
            category=body.category or "syslog",
            facility=body.facility or body.event_type,
            correlation_key=body.correlation_key,
            fields=body.fields,
        )
    else:
        alarm = await correlator.handle_event(
            source_host=body.source_host,
            event_type=body.event_type or "customEvent",
            message=body.message,
            severity=body.severity,
            category=body.category or "custom",
            correlation_key=body.correlation_key,
            fields=body.fields,
        )
    return AlarmRead.model_validate(alarm) if alarm is not None else None


@router.get("/filters", response_model=list[SavedFilterRead])
async def list_saved_alarm_filters(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_api_auth)],
    owner: Optional[str] = None,
) -> list[SavedFilterRead]:
    stmt = select(SavedAlarmFilter).where(
        or_(SavedAlarmFilter.is_public.is_(True), SavedAlarmFilter.owner == principal.subject)
    )
    if owner:
        stmt = stmt.where(SavedAlarmFilter.owner == owner)
    stmt = stmt.order_by(SavedAlarmFilter.name.asc())
    result = await db.execute(stmt)
    return [SavedFilterRead.model_validate(item) for item in result.scalars().all()]


@router.post("/filters", response_model=SavedFilterRead, status_code=status.HTTP_201_CREATED)
async def create_saved_alarm_filter(
    body: SavedFilterCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_api_auth)],
) -> SavedFilterRead:
    saved_filter = SavedAlarmFilter(
        name=body.name,
        owner=principal.subject,
        is_public=body.is_public,
        filters=body.filters,
    )
    db.add(saved_filter)
    await db.flush()
    await db.refresh(saved_filter)
    return SavedFilterRead.model_validate(saved_filter)


@router.patch("/filters/{id}", response_model=SavedFilterRead)
async def update_saved_alarm_filter(
    id: uuid.UUID,
    body: SavedFilterUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_api_auth)],
) -> SavedFilterRead:
    result = await db.execute(select(SavedAlarmFilter).where(SavedAlarmFilter.id == id))
    saved_filter = result.scalar_one_or_none()
    if saved_filter is None:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    if saved_filter.owner != principal.subject:
        raise HTTPException(status_code=403, detail="Only the owner can update this saved filter")
    if body.name is not None:
        saved_filter.name = body.name
    if body.is_public is not None:
        saved_filter.is_public = body.is_public
    if body.filters is not None:
        saved_filter.filters = body.filters
    saved_filter.updated_at = datetime.now()
    await db.flush()
    await db.refresh(saved_filter)
    return SavedFilterRead.model_validate(saved_filter)


@router.delete("/filters/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_alarm_filter(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_api_auth)],
) -> None:
    result = await db.execute(select(SavedAlarmFilter).where(SavedAlarmFilter.id == id))
    saved_filter = result.scalar_one_or_none()
    if saved_filter is None:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    if saved_filter.owner != principal.subject:
        raise HTTPException(status_code=403, detail="Only the owner can delete this saved filter")
    await db.delete(saved_filter)


@router.get("/{id}", response_model=AlarmRead)
async def get_alarm(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    return AlarmRead.model_validate(alarm)


@router.post("/{id}/ack", response_model=AlarmRead)
async def ack_alarm(
    id: uuid.UUID,
    body: AlarmAck,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    alarm.state = "acknowledged"
    alarm.ack_by = body.by_user
    await _audit_alarm_action(
        db,
        alarm=alarm,
        actor=body.by_user,
        action="alarm.acknowledge",
        message=f"Alarm acknowledged by {body.by_user}",
    )
    await db.flush()
    await db.refresh(alarm)
    return AlarmRead.model_validate(alarm)


@router.post("/{id}/clear", response_model=AlarmRead)
async def clear_alarm(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    alarm.state = "cleared"
    alarm.cleared_at = datetime.now()
    await _audit_alarm_action(
        db,
        alarm=alarm,
        actor=None,
        action="alarm.clear",
        message="Alarm manually cleared",
    )
    await db.flush()
    await db.refresh(alarm)
    return AlarmRead.model_validate(alarm)


@router.post("/{id}/suppress", response_model=AlarmRead)
async def suppress_alarm(
    id: uuid.UUID,
    body: AlarmSuppress,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    now = datetime.now()
    raw = dict(alarm.raw_varbinds or {})
    raw["_suppression"] = {
        "by": body.by_user,
        "reason": body.reason,
        "suppressed_at": now.isoformat(),
    }
    alarm.state = "suppressed"
    alarm.ack_by = body.by_user
    alarm.raw_varbinds = raw
    alarm.last_seen = now
    await _audit_alarm_action(
        db,
        alarm=alarm,
        actor=body.by_user,
        action="alarm.suppress",
        message=f"Alarm suppressed by {body.by_user}",
        details={"reason": body.reason},
    )
    await db.flush()
    await db.refresh(alarm)
    return AlarmRead.model_validate(alarm)


@router.post("/{id}/unsuppress", response_model=AlarmRead)
async def unsuppress_alarm(
    id: uuid.UUID,
    body: AlarmAck,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    raw = dict(alarm.raw_varbinds or {})
    raw.pop("_suppression", None)
    alarm.raw_varbinds = raw or None
    alarm.state = "active"
    alarm.last_seen = datetime.now()
    await _audit_alarm_action(
        db,
        alarm=alarm,
        actor=body.by_user,
        action="alarm.unsuppress",
        message=f"Alarm unsuppressed by {body.by_user}",
    )
    await db.flush()
    await db.refresh(alarm)
    return AlarmRead.model_validate(alarm)


@router.websocket("/ws")
async def alarm_websocket(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            ts = datetime.now().isoformat()
            await ws.send_json({"type": "hb", "ts": ts})
            try:
                # Wait up to 30s for a client message; if none, loop sends heartbeat
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)


async def broadcast_alarm(alarm_dict: dict) -> None:
    """Broadcast an alarm dict to all connected WebSocket clients."""
    dead: set[WebSocket] = set()
    for ws in _ws_clients:
        try:
            await ws.send_json({"type": "alarm", "data": alarm_dict})
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)
