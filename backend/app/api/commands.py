"""Commands API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database import async_session_factory
from app.models.command import Command
from app.security.audit import audit
from app.services.ssh.command_runner import CommandRunner

router = APIRouter()


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


async def _get_or_404(db: AsyncSession, cmd_id: uuid.UUID) -> Command:
    result = await db.execute(select(Command).where(Command.id == cmd_id))
    cmd = result.scalar_one_or_none()
    if cmd is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return cmd


@router.get("", response_model=list[CommandRead])
async def list_commands(db: Annotated[AsyncSession, Depends(get_db)]) -> list[CommandRead]:
    result = await db.execute(select(Command))
    return [CommandRead.model_validate(c) for c in result.scalars().all()]


@router.post("", response_model=CommandRead, status_code=status.HTTP_201_CREATED)
async def create_command(
    body: CommandCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommandRead:
    cmd = Command(**body.model_dump())
    db.add(cmd)
    await db.flush()
    await db.refresh(cmd)
    return CommandRead.model_validate(cmd)


@router.get("/{id}", response_model=CommandRead)
async def get_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommandRead:
    cmd = await _get_or_404(db, id)
    return CommandRead.model_validate(cmd)


@router.patch("/{id}", response_model=CommandRead)
async def update_command(
    id: uuid.UUID,
    body: CommandUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommandRead:
    cmd = await _get_or_404(db, id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cmd, field, value)
    await db.flush()
    await db.refresh(cmd)
    return CommandRead.model_validate(cmd)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    cmd = await _get_or_404(db, id)
    await db.delete(cmd)


@router.post("/{id}/run")
async def run_command(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    runner = CommandRunner(session_factory=async_session_factory)
    result = await runner.run_saved_command(id)
    audit("command.run_saved", target=str(id), exit_status=result.exit_status)
    return result.__dict__ if hasattr(result, "__dict__") else result


@router.post("/run-ad-hoc")
async def run_ad_hoc(
    body: AdHocRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    runner = CommandRunner(session_factory=async_session_factory)
    result = await runner.run_ad_hoc(device_id=body.device_id, cli=body.cli)
    audit("command.run_ad_hoc", target=str(body.device_id), exit_status=result.exit_status)
    return result.__dict__ if hasattr(result, "__dict__") else result
