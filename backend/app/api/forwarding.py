"""Event forwarding target API."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.forwarding import ForwardingTarget
from app.schemas.forwarding import (
    ForwardingTargetCreate,
    ForwardingTargetRead,
    ForwardingTargetUpdate,
    ForwardingTestResult,
)
from app.services.forwarding.engine import ForwardingEngine

router = APIRouter()


async def _get_or_404(db: AsyncSession, target_id: uuid.UUID) -> ForwardingTarget:
    target = await db.get(ForwardingTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Forwarding target not found")
    return target


async def _ensure_unique_name(db: AsyncSession, name: str, current_id: uuid.UUID | None = None) -> None:
    stmt = select(ForwardingTarget).where(ForwardingTarget.name == name)
    if current_id is not None:
        stmt = stmt.where(ForwardingTarget.id != current_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Forwarding target name already exists")


@router.get("/targets", response_model=list[ForwardingTargetRead])
async def list_forwarding_targets(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ForwardingTargetRead]:
    result = await db.execute(select(ForwardingTarget).order_by(ForwardingTarget.name.asc()))
    return [ForwardingTargetRead.model_validate(target) for target in result.scalars().all()]


@router.post("/targets", response_model=ForwardingTargetRead, status_code=status.HTTP_201_CREATED)
async def create_forwarding_target(
    body: ForwardingTargetCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardingTargetRead:
    await _ensure_unique_name(db, body.name)
    target = ForwardingTarget(**body.model_dump())
    db.add(target)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Forwarding target name already exists") from exc
    await db.refresh(target)
    return ForwardingTargetRead.model_validate(target)


@router.get("/targets/{id}", response_model=ForwardingTargetRead)
async def get_forwarding_target(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardingTargetRead:
    return ForwardingTargetRead.model_validate(await _get_or_404(db, id))


@router.patch("/targets/{id}", response_model=ForwardingTargetRead)
async def update_forwarding_target(
    id: uuid.UUID,
    body: ForwardingTargetUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardingTargetRead:
    target = await _get_or_404(db, id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        await _ensure_unique_name(db, data["name"], current_id=id)
    for key, value in data.items():
        setattr(target, key, value)
    target.updated_at = datetime.now(timezone.utc)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Forwarding target name already exists") from exc
    await db.refresh(target)
    return ForwardingTargetRead.model_validate(target)


@router.delete("/targets/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_forwarding_target(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    target = await _get_or_404(db, id)
    await db.delete(target)


@router.post("/targets/{id}/test", response_model=ForwardingTestResult)
async def test_forwarding_target(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ForwardingTestResult:
    target = await _get_or_404(db, id)
    ok, message = await ForwardingEngine.test_target(target)
    return ForwardingTestResult(ok=ok, message=message)
