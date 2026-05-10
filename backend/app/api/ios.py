"""IOS version API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ios_version import IOSVersion
from app.services.ios.version_manager import IOSVersionManager

router = APIRouter()


class IOSVersionRead(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    device_id: uuid.UUID
    image_file: str | None = None
    version: str | None = None
    platform: str | None = None
    boot_image: str | None = None
    is_eol: bool = False
    is_eos: bool = False


@router.get("/devices/{id}/versions", response_model=list[IOSVersionRead])
async def list_versions(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[IOSVersionRead]:
    result = await db.execute(select(IOSVersion).where(IOSVersion.device_id == id))
    return [IOSVersionRead.model_validate(v) for v in result.scalars().all()]


@router.post("/devices/{id}/detect")
async def detect_version(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    manager = IOSVersionManager(db=db)
    result = await manager.detect_version(device_id=id)
    return result if isinstance(result, dict) else {"result": result}


@router.get("/eol-report", response_model=list[IOSVersionRead])
async def eol_report(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[IOSVersionRead]:
    """Return latest IOSVersion per device where is_eol or is_eos is True."""
    # Subquery: max id per device (latest record)
    from sqlalchemy import func
    subq = (
        select(func.max(IOSVersion.id).label("max_id"))
        .group_by(IOSVersion.device_id)
        .subquery()
    )
    stmt = (
        select(IOSVersion)
        .where(IOSVersion.id.in_(select(subq.c.max_id)))
        .where((IOSVersion.is_eol == True) | (IOSVersion.is_eos == True))  # noqa: E712
    )
    result = await db.execute(stmt)
    return [IOSVersionRead.model_validate(v) for v in result.scalars().all()]
