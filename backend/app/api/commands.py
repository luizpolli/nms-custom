"""Commands API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.command import Command
from app.services.ssh.command_runner import CommandRunner

router = APIRouter()


class CommandBase(BaseModel):
    device_id: uuid.UUID
    name: str
    cli_command: str
    output_path: str | None = None


class CommandCreate(CommandBase):
    pass


class CommandUpdate(BaseModel):
    name: str | None = None
    cli_command: str | None = None
    output_path: str | None = None


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
    cli: str


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
    runner = CommandRunner(db=db)
    return await runner.run_saved_command(id)


@router.post("/run-ad-hoc")
async def run_ad_hoc(
    body: AdHocRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    runner = CommandRunner(db=db)
    return await runner.run_ad_hoc(device_id=body.device_id, cli=body.cli)
