"""IOS version API routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.credential import Credential
from app.models.device import Device
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
) -> dict[str, object]:
    """Trigger live IOS version detection for a device via SSH."""
    device = await db.get(Device, id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.credential_id is None:
        raise HTTPException(status_code=422, detail="Device has no credential assigned")
    credential = await db.get(Credential, device.credential_id)
    if credential is None:
        raise HTTPException(status_code=422, detail="Credential not found for device")
    manager = IOSVersionManager(session_factory=async_session_factory)
    ios_version = await manager.detect_version(device=device, credential=credential)
    return {
        "id": str(ios_version.id),
        "device_id": str(ios_version.device_id),
        "version": ios_version.version,
        "platform": ios_version.platform,
        "is_eol": ios_version.is_eol,
        "is_eos": ios_version.is_eos,
    }


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
