"""Device API routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db
from app.models.device import Device
from app.models.inventory import Inventory
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.security.crypto import CredentialVault
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential
from app.services.kpi.engine import KPIEngine

router = APIRouter()
settings = Settings()


async def _get_device_or_404(db: AsyncSession, device_id: uuid.UUID) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _build_snmp_cred(device: Device) -> SNMPCredential:
    if not device.credential:
        raise HTTPException(status_code=422, detail="Device has no credential attached")
    cred = device.credential
    vault = CredentialVault.from_settings(settings)
    plain = vault.decrypt(cred.auth_key, cred.id.bytes)
    return SNMPCredential(
        version=cred.snmp_version,
        community=plain,
        username=cred.username,
    )


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = None,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[DeviceRead]:
    stmt = select(Device)
    if q:
        stmt = stmt.where(Device.name.ilike(f"%{q}%") | Device.ip_address.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Device.status == status)
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if tag:
        stmt = stmt.where(Device.tags.any(tag))
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    devices = result.scalars().all()
    return [DeviceRead.model_validate(d) for d in devices]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = Device(**body.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return DeviceRead.model_validate(device)


@router.get("/{id}", response_model=DeviceRead)
async def get_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = await _get_device_or_404(db, id)
    return DeviceRead.model_validate(device)


@router.patch("/{id}", response_model=DeviceRead)
async def update_device(
    id: uuid.UUID,
    body: DeviceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = await _get_device_or_404(db, id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    await db.flush()
    await db.refresh(device)
    return DeviceRead.model_validate(device)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    device = await _get_device_or_404(db, id)
    await db.delete(device)


@router.post("/{id}/poll")
async def poll_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    engine = KPIEngine(db)
    kpis_written = await engine.poll_device(device, snmp_cred)
    return {"kpis_written": kpis_written}


@router.post("/{id}/discover-neighbors")
async def discover_neighbors(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    snmp = SNMPEngine()
    lldp = await snmp.discover_lldp_neighbors(device.ip_address, snmp_cred)
    cdp = await snmp.discover_cdp_neighbors(device.ip_address, snmp_cred)
    return lldp + cdp


@router.get("/{id}/inventory")
async def get_inventory(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    device = await _get_device_or_404(db, id)
    result = await db.execute(select(Inventory).where(Inventory.device_id == id))
    inv = result.scalar_one_or_none()
    return inv
