"""Services API — CRUD for logical service groupings."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.service import Service, ServiceDependency, ServiceMember

router = APIRouter()


_VALID_DIRECTIONS = {"source_to_target", "target_to_source", "bidirectional"}
_VALID_OVERRIDES = {"auto", "source_to_target", "target_to_source", "bidirectional", "none"}


class ServiceDependencyRead(BaseModel):
    id: uuid.UUID
    source_service_id: uuid.UUID
    target_service_id: uuid.UUID
    source_service_name: str | None = None
    target_service_name: str | None = None
    dependency_type: str
    direction: str
    direction_override: str = "auto"
    effective_direction: str = "source_to_target"
    weight: float
    is_critical: bool
    description: str | None = None
    created_at: datetime


class ServiceDependencyCreate(BaseModel):
    target_service_id: uuid.UUID
    dependency_type: str = "depends_on"
    direction: str = "source_to_target"
    direction_override: str = "auto"
    weight: float = 1.0
    is_critical: bool = False
    description: str | None = None


class ServiceDependencyUpdate(BaseModel):
    dependency_type: str | None = None
    direction: str | None = None
    direction_override: str | None = None
    weight: float | None = Field(default=None, ge=0.0, le=10.0)
    is_critical: bool | None = None
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
    target_score: int | None = None
    member_count: int
    created_at: datetime
    updated_at: datetime
    members: list[ServiceMemberRead] = Field(default_factory=list)
    dependencies: list[ServiceDependencyRead] = Field(default_factory=list)


class ServiceCreate(BaseModel):
    name: str
    kind: str = "other"
    description: str | None = None
    target_score: int | None = None
    members: list[ServiceMemberCreate] = Field(default_factory=list)


class ServiceUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    description: str | None = None
    target_score: int | None = Field(default=None, ge=0, le=100)


def _effective_direction(d: ServiceDependency) -> str:
    override = getattr(d, "direction_override", "auto") or "auto"
    if override == "auto" or override == "none":
        return d.direction
    return override


def _to_dependency_read(d: ServiceDependency) -> ServiceDependencyRead:
    override = getattr(d, "direction_override", "auto") or "auto"
    return ServiceDependencyRead(
        id=d.id,
        source_service_id=d.source_service_id,
        target_service_id=d.target_service_id,
        source_service_name=d.source_service.name if d.source_service else None,
        target_service_name=d.target_service.name if d.target_service else None,
        dependency_type=d.dependency_type,
        direction=d.direction,
        direction_override=override,
        effective_direction=_effective_direction(d),
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
        target_score=s.target_score,
        member_count=len(members),
        created_at=s.created_at,
        updated_at=s.updated_at,
        members=[_to_member_read(m) for m in members],
        dependencies=[_to_dependency_read(d) for d in dependencies],
    )


# Eager-load every relationship _to_service_read touches. Without this each
# service triggers two extra queries per upstream dependency (one for
# source_service.name, one for target_service.name) — the classic N+1
# pattern. With this option the whole list is served in a small fixed
# number of queries regardless of fleet size.
_LIST_SERVICE_EAGER = (
    selectinload(Service.members),
    selectinload(Service.upstream_dependencies).selectinload(
        ServiceDependency.source_service
    ),
    selectinload(Service.upstream_dependencies).selectinload(
        ServiceDependency.target_service
    ),
)


@router.get("", response_model=list[ServiceRead])
async def list_services(db: Annotated[AsyncSession, Depends(get_db)]) -> list[ServiceRead]:
    result = await db.execute(
        select(Service).options(*_LIST_SERVICE_EAGER).order_by(Service.name)
    )
    return [_to_service_read(s) for s in result.scalars().all()]


@router.post("", response_model=ServiceRead, status_code=201)
async def create_service(
    body: ServiceCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> ServiceRead:
    existing = await db.execute(select(Service).where(Service.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Service name already exists")
    service = Service(name=body.name, kind=body.kind, description=body.description, target_score=body.target_score)
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
    update_data = body.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] is not None:
        service.name = update_data["name"]
    if "kind" in update_data and update_data["kind"] is not None:
        service.kind = update_data["kind"]
    if "description" in update_data:
        service.description = update_data["description"]
    if "target_score" in update_data:
        service.target_score = update_data["target_score"]
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
    if body.direction not in _VALID_DIRECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid direction: {body.direction}")
    if body.direction_override not in _VALID_OVERRIDES:
        raise HTTPException(status_code=400, detail=f"Invalid direction_override: {body.direction_override}")
    dependency = ServiceDependency(
        source_service_id=service_id,
        target_service_id=body.target_service_id,
        dependency_type=body.dependency_type,
        direction=body.direction,
        direction_override=body.direction_override,
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


@router.patch("/{service_id}/dependencies/{dependency_id}", response_model=ServiceDependencyRead)
async def update_dependency(
    service_id: uuid.UUID,
    dependency_id: uuid.UUID,
    body: ServiceDependencyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceDependencyRead:
    dependency = await db.get(ServiceDependency, dependency_id)
    if not dependency or dependency.source_service_id != service_id:
        raise HTTPException(status_code=404, detail="Dependency not found")
    data = body.model_dump(exclude_unset=True)
    if "direction" in data and data["direction"] is not None:
        if data["direction"] not in _VALID_DIRECTIONS:
            raise HTTPException(status_code=400, detail=f"Invalid direction: {data['direction']}")
        dependency.direction = data["direction"]
    if "direction_override" in data and data["direction_override"] is not None:
        if data["direction_override"] not in _VALID_OVERRIDES:
            raise HTTPException(status_code=400, detail=f"Invalid direction_override: {data['direction_override']}")
        dependency.direction_override = data["direction_override"]
    if "dependency_type" in data and data["dependency_type"] is not None:
        dependency.dependency_type = data["dependency_type"]
    if "weight" in data and data["weight"] is not None:
        dependency.weight = float(data["weight"])
    if "is_critical" in data and data["is_critical"] is not None:
        dependency.is_critical = bool(data["is_critical"])
    if "description" in data:
        dependency.description = data["description"]
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
