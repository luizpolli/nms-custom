"""KPI threshold (TCA) API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.kpi_threshold import KPIThreshold
from app.schemas.kpi_threshold import (
    KPIThresholdCreate,
    KPIThresholdRead,
    KPIThresholdUpdate,
)

router = APIRouter()


async def _get_or_404(db: AsyncSession, threshold_id: uuid.UUID) -> KPIThreshold:
    result = await db.execute(select(KPIThreshold).where(KPIThreshold.id == threshold_id))
    threshold = result.scalar_one_or_none()
    if threshold is None:
        raise HTTPException(status_code=404, detail="KPI threshold not found")
    return threshold


@router.get("", response_model=list[KPIThresholdRead])
async def list_thresholds(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = None,
    kpi_type: str | None = None,
) -> list[KPIThresholdRead]:
    stmt = select(KPIThreshold)
    if enabled is not None:
        stmt = stmt.where(KPIThreshold.enabled == enabled)
    if kpi_type:
        stmt = stmt.where(KPIThreshold.kpi_type == kpi_type)
    stmt = stmt.order_by(KPIThreshold.created_at.asc())
    result = await db.execute(stmt)
    return [KPIThresholdRead.model_validate(t) for t in result.scalars().all()]


@router.post("", response_model=KPIThresholdRead, status_code=status.HTTP_201_CREATED)
async def create_threshold(
    body: KPIThresholdCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KPIThresholdRead:
    threshold = KPIThreshold(**body.model_dump())
    db.add(threshold)
    await db.flush()
    await db.refresh(threshold)
    return KPIThresholdRead.model_validate(threshold)


@router.get("/{id}", response_model=KPIThresholdRead)
async def get_threshold(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KPIThresholdRead:
    threshold = await _get_or_404(db, id)
    return KPIThresholdRead.model_validate(threshold)


@router.patch("/{id}", response_model=KPIThresholdRead)
async def update_threshold(
    id: uuid.UUID,
    body: KPIThresholdUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KPIThresholdRead:
    threshold = await _get_or_404(db, id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(threshold, key, value)
    threshold.updated_at = datetime.now()
    await db.flush()
    await db.refresh(threshold)
    return KPIThresholdRead.model_validate(threshold)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_threshold(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    threshold = await _get_or_404(db, id)
    await db.delete(threshold)
