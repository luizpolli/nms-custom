"""Alarms API routes — REST + WebSocket."""

from __future__ import annotations

import asyncio
import csv
import io
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
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
    model_config = {"from_attributes": True, "populate_by_name": True}
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
    acknowledged_by: str | None = Field(default=None, validation_alias="ack_by")
    occurrence_count: int
    raw_varbinds: dict | None = None


class AlarmHistoryEntry(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    timestamp: datetime
    actor: str | None = None
    action: str
    outcome: str
    message: str | None = None
    details: dict | None = None


class AlarmAck(BaseModel):
    by_user: str


class BulkAlarmAck(BaseModel):
    alarm_ids: list[uuid.UUID]
    by_user: str


class BulkAlarmClear(BaseModel):
    alarm_ids: list[uuid.UUID]


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
    info: int = 0
    clear: int = 0


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
    can_update: bool = False
    can_delete: bool = False


ALARM_EXPORT_COLUMNS = [
    "Alarm ID",
    "Severity",
    "State",
    "Source Host",
    "Category",
    "Event Type",
    "Message",
    "Trap OID",
    "Correlation Key",
    "First Seen",
    "Last Seen",
    "Cleared At",
    "Acknowledged By",
    "Occurrences",
]


def _is_admin_or_root(principal: Principal) -> bool:
    return principal.role.lower() in {"admin", "root"}


def _saved_filter_read(saved_filter: SavedAlarmFilter, principal: Principal) -> SavedFilterRead:
    payload = SavedFilterRead.model_validate(saved_filter)
    payload.can_update = saved_filter.owner == principal.subject
    payload.can_delete = _is_admin_or_root(principal)
    return payload


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


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _alarm_filters_stmt(
    *,
    alarm_ids: list[uuid.UUID] | None = None,
    device_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    source_host: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    stmt = select(Alarm)
    if alarm_ids:
        stmt = stmt.where(Alarm.id.in_(alarm_ids))
    if device_id:
        stmt = stmt.where(Alarm.device_id == device_id)
    if object_type:
        stmt = stmt.where(Alarm.object_type == object_type)
    if object_id:
        stmt = stmt.where(Alarm.object_id == object_id)
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
    return stmt


@router.get("", response_model=list[AlarmRead])
async def list_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    source_host: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AlarmRead]:
    stmt = _alarm_filters_stmt(
        device_id=device_id,
        object_type=object_type,
        object_id=object_id,
        severity=severity,
        state=state,
        category=category,
        event_type=event_type,
        source_host=source_host,
        q=q,
        since=since,
        until=until,
    )
    stmt = stmt.order_by(Alarm.last_seen.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return [AlarmRead.model_validate(a) for a in result.scalars().all()]


@router.get("/export")
async def export_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    export_format: str = Query("csv", alias="format", pattern="^csv$"),
    alarm_ids: list[uuid.UUID] | None = Query(None),
    device_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    severity: str | None = None,
    state: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    source_host: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    """Export selected alarms or all alarms matching the current filters."""
    del export_format
    stmt = _alarm_filters_stmt(
        alarm_ids=alarm_ids,
        device_id=device_id,
        object_type=object_type,
        object_id=object_id,
        severity=severity,
        state=state,
        category=category,
        event_type=event_type,
        source_host=source_host,
        q=q,
        since=since,
        until=until,
    ).order_by(Alarm.last_seen.desc())
    result = await db.execute(stmt)
    alarms = result.scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ALARM_EXPORT_COLUMNS)
    writer.writeheader()
    for alarm in alarms:
        writer.writerow(
            {
                "Alarm ID": _csv_value(alarm.id),
                "Severity": _csv_value(alarm.severity),
                "State": _csv_value(alarm.state),
                "Source Host": _csv_value(alarm.source_host),
                "Category": _csv_value(alarm.category),
                "Event Type": _csv_value(alarm.event_type),
                "Message": _csv_value(alarm.message),
                "Trap OID": _csv_value(alarm.trap_oid),
                "Correlation Key": _csv_value(alarm.correlation_key),
                "First Seen": _csv_value(alarm.first_seen),
                "Last Seen": _csv_value(alarm.last_seen),
                "Cleared At": _csv_value(alarm.cleared_at),
                "Acknowledged By": _csv_value(alarm.ack_by),
                "Occurrences": _csv_value(alarm.occurrence_count),
            }
        )

    filename = "alarms_selected_export.csv" if alarm_ids else "alarms_export.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    info = await _count(Alarm.severity == "info")
    clear_count = await _count(Alarm.severity == "clear")
    return AlarmSummary(
        total=total, active=active, cleared=cleared, acknowledged=acknowledged,
        critical=critical, major=major, minor=minor, warning=warning,
        info=info, clear=clear_count,
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
    owner: str | None = None,
) -> list[SavedFilterRead]:
    stmt = select(SavedAlarmFilter).where(
        or_(SavedAlarmFilter.is_public.is_(True), SavedAlarmFilter.owner == principal.subject)
    )
    if owner:
        stmt = stmt.where(SavedAlarmFilter.owner == owner)
    stmt = stmt.order_by(SavedAlarmFilter.name.asc())
    result = await db.execute(stmt)
    return [_saved_filter_read(item, principal) for item in result.scalars().all()]


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
    return _saved_filter_read(saved_filter, principal)


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
    return _saved_filter_read(saved_filter, principal)


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
    if not _is_admin_or_root(principal):
        raise HTTPException(status_code=403, detail="Only admin or root can delete saved filters")
    await db.delete(saved_filter)


@router.get("/{id}", response_model=AlarmRead)
async def get_alarm(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRead:
    alarm = await _get_or_404(db, id)
    return AlarmRead.model_validate(alarm)


@router.get("/{id}/history", response_model=list[AlarmHistoryEntry])
async def get_alarm_history(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 200,
) -> list[AlarmHistoryEntry]:
    await _get_or_404(db, id)
    stmt = (
        select(AuditLog)
        .where(AuditLog.object_type == "alarm", AuditLog.object_id == str(id))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [AlarmHistoryEntry.model_validate(row) for row in result.scalars().all()]


@router.post("/bulk-ack")
async def bulk_ack_alarms(
    body: BulkAlarmAck,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    if not body.alarm_ids:
        return {"acknowledged": 0}

    result = await db.execute(select(Alarm).where(Alarm.id.in_(body.alarm_ids)))
    alarms = result.scalars().all()
    now = datetime.now()
    for alarm in alarms:
        alarm.state = "acknowledged"
        alarm.ack_by = body.by_user
        alarm.last_seen = now
        await _audit_alarm_action(
            db,
            alarm=alarm,
            actor=body.by_user,
            action="alarm.bulk_acknowledge",
            message=f"Alarm bulk acknowledged by {body.by_user}",
            details={"bulk_alarm_count": len(alarms)},
        )
    await db.flush()
    return {"acknowledged": len(alarms)}


@router.post("/bulk-clear")
async def bulk_clear_alarms(
    body: BulkAlarmClear,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    if not body.alarm_ids:
        return {"cleared": 0}

    result = await db.execute(select(Alarm).where(Alarm.id.in_(body.alarm_ids)))
    alarms = result.scalars().all()
    now = datetime.now()
    for alarm in alarms:
        alarm.state = "cleared"
        alarm.cleared_at = now
        alarm.last_seen = now
        await _audit_alarm_action(
            db,
            alarm=alarm,
            actor=None,
            action="alarm.bulk_clear",
            message="Alarm bulk cleared",
            details={"bulk_alarm_count": len(alarms)},
        )
    await db.flush()
    return {"cleared": len(alarms)}


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
            except TimeoutError:
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
