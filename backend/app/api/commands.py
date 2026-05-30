"""Commands API routes — single-device, bulk, schedule, history, export."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.command import Command
from app.models.command_run import CommandRun
from app.models.device import Device
from app.security.allowlist import assert_command_allowed
from app.security.audit import audit
from app.security.auth import (
    PERM_COMMANDS_CREATE,
    PERM_COMMANDS_DELETE,
    PERM_COMMANDS_EXPORT,
    PERM_COMMANDS_READ,
    PERM_COMMANDS_RUN,
    PERM_COMMANDS_RUN_BULK,
    PERM_COMMANDS_UPDATE,
    Principal,
    require_command_permission,
)
from app.services.command_export import CONTENT_TYPES, RENDERERS, export_to_file
from app.services.email_sender import send_email
from app.services.ssh.command_runner import CommandRunner

router = APIRouter()

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CommandBase(BaseModel):
    device_id: uuid.UUID
    name: str = Field(..., max_length=128)
    cli_command: str = Field(..., min_length=1, max_length=512)
    output_path: str | None = Field(None, max_length=255)

    @field_validator("cli_command")
    @classmethod
    def validate_cli(cls, value: str) -> str:
        if any(ch in value for ch in "\r\n\x00"):
            raise ValueError("CLI command contains invalid control characters")
        return value


class CommandCreate(CommandBase):
    pass


class CommandUpdate(BaseModel):
    device_id: uuid.UUID | None = None
    name: str | None = None
    cli_command: str | None = Field(None, max_length=512)
    output_path: str | None = None

    @field_validator("cli_command")
    @classmethod
    def validate_cli(cls, value: str | None) -> str | None:
        if value is not None and any(ch in value for ch in "\r\n\x00"):
            raise ValueError("CLI command contains invalid control characters")
        return value


class CommandRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    device_id: uuid.UUID
    name: str
    cli_command: str
    output_path: str | None = None
    last_output: str | None = None


class AdHocRequest(BaseModel):
    device_id: uuid.UUID
    cli: str = Field(..., min_length=1, max_length=512)

    @field_validator("cli")
    @classmethod
    def validate_cli(cls, value: str) -> str:
        if any(ch in value for ch in "\r\n\x00"):
            raise ValueError("CLI command contains invalid control characters")
        return value


class BulkRunRequest(BaseModel):
    device_ids: list[uuid.UUID] = Field(default_factory=list)
    device_group_id: uuid.UUID | None = None  # reserved for future group table
    tag: str | None = None


class BulkRunResult(BaseModel):
    device_id: str
    exit_status: int | None
    stdout: str | None
    stderr: str | None
    error: str | None


class CommandRunRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    command_id: uuid.UUID | None
    device_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    exit_status: int | None
    stdout: str | None
    stderr: str | None
    triggered_by: str


class ExportRequest(BaseModel):
    format: Literal["txt", "json", "csv"] = "txt"
    delivery: Literal["download", "email", "file"] = "download"
    recipients: list[str] = Field(default_factory=list)
    target_path: str | None = None  # filename within artifacts dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_or_404(db: AsyncSession, cmd_id: uuid.UUID) -> Command:
    result = await db.execute(select(Command).where(Command.id == cmd_id))
    cmd = result.scalar_one_or_none()
    if cmd is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return cmd


async def _resolve_device_ids(db: AsyncSession, body: BulkRunRequest) -> list[uuid.UUID]:
    """Resolve explicit device_ids + optional tag filter into a deduplicated list."""
    ids: set[uuid.UUID] = set(body.device_ids)
    if body.tag:
        stmt = select(Device.id).where(Device.tags.any(body.tag))
        rows = await db.execute(stmt)
        ids.update(r for (r,) in rows.fetchall())
    if not ids:
        raise HTTPException(status_code=422, detail="No devices resolved for bulk run")
    return list(ids)


def _serialize_run(run: CommandRun) -> dict:
    return {
        "device_id": str(run.device_id),
        "exit_status": run.exit_status,
        "stdout": run.stdout,
        "stderr": run.stderr,
        "error": None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[CommandRead])
async def list_commands(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
) -> list[CommandRead]:
    result = await db.execute(select(Command))
    return [CommandRead.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=CommandRead, status_code=status.HTTP_201_CREATED)
async def create_command(
    body: CommandCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_CREATE))],
) -> CommandRead:
    assert_command_allowed(body.cli_command)
    cmd = Command(**body.model_dump())
    db.add(cmd)
    await db.flush()
    await db.refresh(cmd)
    audit("command.create", target=str(cmd.id))
    return CommandRead.model_validate(cmd)


@router.get("/{id}", response_model=CommandRead)
async def get_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
) -> CommandRead:
    cmd = await _get_or_404(db, id)
    return CommandRead.model_validate(cmd)


@router.patch("/{id}", response_model=CommandRead)
async def update_command(
    id: uuid.UUID,
    body: CommandUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_UPDATE))],
) -> CommandRead:
    cmd = await _get_or_404(db, id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "cli_command" and value is not None:
            assert_command_allowed(value)
        setattr(cmd, field, value)
    await db.flush()
    await db.refresh(cmd)
    audit("command.update", target=str(id))
    return CommandRead.model_validate(cmd)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_DELETE))],
) -> None:
    cmd = await _get_or_404(db, id)
    await db.delete(cmd)
    audit("command.delete", target=str(id))


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------


@router.post("/{id}/run")
async def run_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_RUN))],
) -> dict:
    runner = CommandRunner(session_factory=async_session_factory)
    result = await runner.run_saved_command(id)
    audit("command.run_saved", target=str(id), exit_status=result.exit_status)
    return result.__dict__ if hasattr(result, "__dict__") else result


@router.post("/run-ad-hoc")
async def run_ad_hoc(
    body: AdHocRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_RUN))],
) -> dict:
    assert_command_allowed(body.cli)
    runner = CommandRunner(session_factory=async_session_factory)
    result = await runner.run_ad_hoc(device_id=body.device_id, cli=body.cli)
    audit("command.run_ad_hoc", target=str(body.device_id), exit_status=result.exit_status)
    return result.__dict__ if hasattr(result, "__dict__") else result


@router.post("/{id}/run-bulk", response_model=list[BulkRunResult])
async def run_bulk(
    id: uuid.UUID,
    body: BulkRunRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_RUN_BULK))],
) -> list[BulkRunResult]:
    await _get_or_404(db, id)
    device_ids = await _resolve_device_ids(db, body)
    runner = CommandRunner(session_factory=async_session_factory)
    results = await runner.run_bulk(id, device_ids)
    audit("command.run_bulk", target=str(id), device_count=len(device_ids))
    return [BulkRunResult(**r) for r in results]


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------


@router.get("/{id}/runs", response_model=list[CommandRunRead])
async def list_runs(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
    limit: int = 100,
) -> list[CommandRunRead]:
    await _get_or_404(db, id)
    stmt = (
        select(CommandRun)
        .where(CommandRun.command_id == id)
        .order_by(CommandRun.started_at.desc())
        .limit(min(limit, 500))
    )
    result = await db.execute(stmt)
    return [CommandRunRead.model_validate(r) for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.post("/{id}/runs/export")
async def export_runs(
    id: uuid.UUID,
    body: ExportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_EXPORT))],
) -> Response:
    await _get_or_404(db, id)
    stmt = (
        select(CommandRun)
        .where(CommandRun.command_id == id)
        .order_by(CommandRun.started_at.desc())
        .limit(500)
    )
    result = await db.execute(stmt)
    runs = [_serialize_run(r) for r in result.scalars().all()]

    renderer = RENDERERS[body.format]
    data = renderer(runs)
    content_type = CONTENT_TYPES[body.format]
    filename = f"command_{id}_runs.{body.format}"

    audit("command.export", target=str(id), delivery=body.delivery, format=body.format)

    if body.delivery == "download":
        return Response(
            content=data,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if body.delivery == "email":
        if not body.recipients:
            raise HTTPException(status_code=422, detail="recipients required for email delivery")
        sent = send_email(
            recipients=body.recipients,
            subject=f"Command run export — {id}",
            body=f"Attached: {filename}",
            attachment_bytes=data,
            attachment_filename=filename,
            attachment_mimetype=content_type,
        )
        return Response(
            content=f'{{"sent": {str(sent).lower()}, "filename": "{filename}"}}',
            media_type="application/json",
        )

    # delivery == "file"
    safe_name = body.target_path or filename
    try:
        path = export_to_file(safe_name, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=f'{{"path": "{path}", "filename": "{path.name}"}}',
        media_type="application/json",
    )
