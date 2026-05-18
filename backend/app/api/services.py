"""Services API — CRUD for logical service groupings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.service import Service, ServiceDependency, ServiceMember

router = APIRouter()


class ServiceDependencyRead(BaseModel):
    id: uuid.UUID
    source_service_id: uuid.UUID
    target_service_id: uuid.UUID
    source_service_name: str | None = None
    target_service_name: str | None = None
    dependency_type: str
    direction: str
    weight: float
    is_critical: bool
    description: str | None = None
    created_at: datetime


class ServiceDependencyCreate(BaseModel):
    target_service_id: uuid.UUID
    dependency_type: str = "depends_on"
    direction: str = "source_to_target"
    weight: float = 1.0
    is_critical: bool = False
    description: str | None = None


class ServiceMemberRead(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID | None = None
    interface_id: uuid.UUID | None = None
    role: str
    weight: float


class ServiceMemberCreate(BaseModel):
    device_id: uuid.UUID | None = None
    interface_id: uuid.UUID | None = None
    role: str = "member"
    weight: float = 1.0


class ServiceRead(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    description: str | None = None
    member_count: int
    created_at: datetime
    updated_at: datetime
    members: list[ServiceMemberRead] = Field(default_factory=list)
    dependencies: list[ServiceDependencyRead] = Field(default_factory=list)


class ServiceCreate(BaseModel):
    name: str
    kind: str = "other"
    description: str | None = None
    members: list[ServiceMemberCreate] = Field(default_factory=list)


class ServiceUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    description: str | None = None


def _to_dependency_read(d: ServiceDependency) -> ServiceDependencyRead:
    return ServiceDependencyRead(
        id=d.id,
        source_service_id=d.source_service_id,
        target_service_id=d.target_service_id,
        source_service_name=d.source_service.name if d.source_service else None,
        target_service_name=d.target_service.name if d.target_service else None,
        dependency_type=d.dependency_type,
        direction=d.direction,
        weight=d.weight,
        is_critical=d.is_critical,
        description=d.description,
        created_at=d.created_at,
    )


def _to_member_read(m: ServiceMember) -> ServiceMemberRead:
    return ServiceMemberRead(
        id=m.id,
        device_id=m.device_id,
        interface_id=m.interface_id,
        role=m.role,
        weight=m.weight,
    )


def _to_service_read(s: Service) -> ServiceRead:
    members = list(s.members or [])
    dependencies = list(s.upstream_dependencies or [])
    return ServiceRead(
        id=s.id,
        name=s.name,
        kind=s.kind,
        description=s.description,
        member_count=len(members),
        created_at=s.created_at,
        updated_at=s.updated_at,
        members=[_to_member_read(m) for m in members],
        dependencies=[_to_dependency_read(d) for d in dependencies],
    )


@router.get("", response_model=list[ServiceRead])
async def list_services(db: Annotated[AsyncSession, Depends(get_db)]) -> list[ServiceRead]:
    result = await db.execute(select(Service).order_by(Service.name))
    return [_to_service_read(s) for s in result.scalars().all()]


@router.post("", response_model=ServiceRead, status_code=201)
async def create_service(
    body: ServiceCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> ServiceRead:
    existing = await db.execute(select(Service).where(Service.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Service name already exists")
    service = Service(name=body.name, kind=body.kind, description=body.description)
    for m in body.members:
        service.members.append(
            ServiceMember(
                device_id=m.device_id,
                interface_id=m.interface_id,
                role=m.role,
                weight=m.weight,
            )
        )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return _to_service_read(service)


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(
    service_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> ServiceRead:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return _to_service_read(service)


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: uuid.UUID,
    body: ServiceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceRead:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if body.name is not None:
        service.name = body.name
    if body.kind is not None:
        service.kind = body.kind
    if body.description is not None:
        service.description = body.description
    await db.flush()
    await db.refresh(service)
    return _to_service_read(service)


@router.delete("/{service_id}", status_code=204)
async def delete_service(
    service_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]
) -> None:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.delete(service)
    await db.flush()


@router.post("/{service_id}/members", response_model=ServiceMemberRead, status_code=201)
async def add_member(
    service_id: uuid.UUID,
    body: ServiceMemberCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceMemberRead:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if not body.device_id and not body.interface_id:
        raise HTTPException(status_code=400, detail="device_id or interface_id required")
    member = ServiceMember(
        service_id=service_id,
        device_id=body.device_id,
        interface_id=body.interface_id,
        role=body.role,
        weight=body.weight,
    )
    db.add(member)
    await db.flush()
    return _to_member_read(member)


@router.post("/{service_id}/dependencies", response_model=ServiceDependencyRead, status_code=201)
async def add_dependency(
    service_id: uuid.UUID,
    body: ServiceDependencyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceDependencyRead:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    target = await db.get(Service, body.target_service_id)
    if not target:
        raise HTTPException(status_code=404, detail="Target service not found")
    if service_id == body.target_service_id:
        raise HTTPException(status_code=400, detail="Service cannot depend on itself")
    existing = await db.execute(
        select(ServiceDependency).where(
            ServiceDependency.source_service_id == service_id,
            ServiceDependency.target_service_id == body.target_service_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Dependency already exists")
    dependency = ServiceDependency(
        source_service_id=service_id,
        target_service_id=body.target_service_id,
        dependency_type=body.dependency_type,
        direction=body.direction,
        weight=body.weight,
        is_critical=body.is_critical,
        description=body.description,
    )
    dependency.source_service = service
    dependency.target_service = target
    db.add(dependency)
    await db.flush()
    await db.refresh(dependency)
    return _to_dependency_read(dependency)


@router.delete("/{service_id}/dependencies/{dependency_id}", status_code=204)
async def remove_dependency(
    service_id: uuid.UUID,
    dependency_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    dependency = await db.get(ServiceDependency, dependency_id)
    if not dependency or dependency.source_service_id != service_id:
        raise HTTPException(status_code=404, detail="Dependency not found")
    await db.delete(dependency)
    await db.flush()


@router.delete("/{service_id}/members/{member_id}", status_code=204)
async def remove_member(
    service_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    member = await db.get(ServiceMember, member_id)
    if not member or member.service_id != service_id:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await db.flush()
