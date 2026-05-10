"""Alarms API routes — REST + WebSocket."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alarm import Alarm

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


class AlarmAck(BaseModel):
    by_user: str


class AlarmSummary(BaseModel):
    total: int
    active: int
    cleared: int
    acknowledged: int
    critical: int
    major: int
    minor: int
    warning: int


async def _get_or_404(db: AsyncSession, alarm_id: uuid.UUID) -> Alarm:
    result = await db.execute(select(Alarm).where(Alarm.id == alarm_id))
    alarm = result.scalar_one_or_none()
    if alarm is None:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm


@router.get("", response_model=list[AlarmRead])
async def list_alarms(
    db: Annotated[AsyncSession, Depends(get_db)],
    device_id: Optional[uuid.UUID] = None,
    severity: Optional[str] = None,
    state: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
) -> list[AlarmRead]:
    stmt = select(Alarm)
    if device_id:
        stmt = stmt.where(Alarm.device_id == device_id)
    if severity:
        stmt = stmt.where(Alarm.severity == severity)
    if state:
        stmt = stmt.where(Alarm.state == state)
    if since:
        stmt = stmt.where(Alarm.first_seen >= since)
    if until:
        stmt = stmt.where(Alarm.first_seen <= until)
    stmt = stmt.order_by(Alarm.last_seen.desc()).limit(limit)
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
