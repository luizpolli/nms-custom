"""Command schedules API — CRUD + run-now."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.command_schedule import CommandSchedule
from app.security.audit import audit
from app.security.auth import (
    PERM_COMMANDS_DELETE,
    PERM_COMMANDS_READ,
    PERM_COMMANDS_SCHEDULE,
    Principal,
    require_command_permission,
)
from app.services.ssh.command_runner import CommandRunner

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CommandScheduleBase(BaseModel):
    name: str = Field(..., max_length=255)
    command_id: uuid.UUID
    device_ids: list[uuid.UUID] = Field(default_factory=list)
    tag: str | None = Field(None, max_length=128)
    cron_expr: str | None = Field(None, max_length=128)
    interval_seconds: int | None = Field(None, ge=60)
    enabled: bool = True


class CommandScheduleCreate(CommandScheduleBase):
    pass


class CommandScheduleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    device_ids: list[uuid.UUID] | None = None
    tag: str | None = None
    cron_expr: str | None = None
    interval_seconds: int | None = Field(None, ge=60)
    enabled: bool | None = None


class CommandScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    command_id: uuid.UUID
    device_ids: list[str]
    tag: str | None
    cron_expr: str | None
    interval_seconds: int | None
    enabled: bool
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class BulkRunResult(BaseModel):
    device_id: str
    exit_status: int | None
    stdout: str | None
    stderr: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_or_404(db: AsyncSession, schedule_id: uuid.UUID) -> CommandSchedule:
    result = await db.execute(select(CommandSchedule).where(CommandSchedule.id == schedule_id))
    sched = result.scalar_one_or_none()
    if sched is None:
        raise HTTPException(status_code=404, detail="Command schedule not found")
    return sched


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CommandScheduleRead])
async def list_schedules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
    enabled: bool | None = None,
) -> list[CommandScheduleRead]:
    stmt = select(CommandSchedule)
    if enabled is not None:
        stmt = stmt.where(CommandSchedule.enabled == enabled)
    stmt = stmt.order_by(CommandSchedule.created_at.asc())
    result = await db.execute(stmt)
    return [CommandScheduleRead.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=CommandScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: CommandScheduleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_SCHEDULE))],
) -> CommandScheduleRead:
    data = body.model_dump()
    data["device_ids"] = [str(d) for d in data.get("device_ids", [])]
    sched = CommandSchedule(**data)
    db.add(sched)
    await db.flush()
    await db.refresh(sched)
    audit("command_schedule.create", target=str(sched.id))
    return CommandScheduleRead.model_validate(sched)


@router.get("/{id}", response_model=CommandScheduleRead)
async def get_schedule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
) -> CommandScheduleRead:
    sched = await _get_or_404(db, id)
    return CommandScheduleRead.model_validate(sched)


@router.patch("/{id}", response_model=CommandScheduleRead)
async def update_schedule(
    id: uuid.UUID,
    body: CommandScheduleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_SCHEDULE))],
) -> CommandScheduleRead:
    sched = await _get_or_404(db, id)
    updates = body.model_dump(exclude_unset=True)
    if "device_ids" in updates and updates["device_ids"] is not None:
        updates["device_ids"] = [str(d) for d in updates["device_ids"]]
    for key, value in updates.items():
        setattr(sched, key, value)
    sched.updated_at = datetime.now()
    await db.flush()
    await db.refresh(sched)
    audit("command_schedule.update", target=str(id))
    return CommandScheduleRead.model_validate(sched)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_DELETE))],
) -> None:
    sched = await _get_or_404(db, id)
    await db.delete(sched)
    audit("command_schedule.delete", target=str(id))


@router.post("/{id}/run-now", response_model=list[BulkRunResult])
async def run_now(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_SCHEDULE))],
) -> list[BulkRunResult]:
    sched = await _get_or_404(db, id)
    device_ids = [uuid.UUID(d) for d in sched.device_ids]
    if not device_ids:
        raise HTTPException(status_code=422, detail="Schedule has no device targets")

    runner = CommandRunner(session_factory=async_session_factory)
    results = await runner.run_bulk(sched.command_id, device_ids, triggered_by="schedule")

    sched.last_run_at = datetime.now()
    errors = [r for r in results if r.get("error")]
    sched.last_status = "error" if errors else "ok"
    sched.last_error = errors[0]["error"] if errors else None
    await db.flush()

    audit("command_schedule.run_now", target=str(id), device_count=len(device_ids))
    return [BulkRunResult(**r) for r in results]
