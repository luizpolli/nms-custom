"""Core device CRUD and persisted-record lookups."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.devices.common import _get_device_or_404, router
from app.database import get_db
from app.models.device import Device
from app.models.interface import Interface
from app.models.inventory import Inventory
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.schemas.interface import InterfaceRead as ManagedInterfaceRead


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    status: str | None = None,
    vendor: str | None = None,
    tag: str | None = None,
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
        stmt = stmt.where(Device.tags.any(tag))  # type: ignore[arg-type]  # ARRAY.any(str) valid for Postgres
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


@router.get("/{id}/managed-interfaces", response_model=list[ManagedInterfaceRead])
async def get_managed_interfaces(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ManagedInterfaceRead]:
    """Return persisted normalized Interface records for service/topology membership."""
    await _get_device_or_404(db, id)
    result = await db.execute(
        select(Interface)
        .where(Interface.device_id == id)
        .order_by(Interface.if_index.asc().nullslast(), Interface.name)
    )
    return [ManagedInterfaceRead.model_validate(interface) for interface in result.scalars().all()]


@router.get("/{id}/inventory")
async def get_inventory(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Called for its side-effect: raises HTTP 404 when the device id is unknown.
    _ = await _get_device_or_404(db, id)
    result = await db.execute(select(Inventory).where(Inventory.device_id == id))
    inv = result.scalar_one_or_none()
    return inv
