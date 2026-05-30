"""Monitoring policy API."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.monitoring_policy import MonitoringPolicy
from app.schemas.monitoring_policy import (
    MonitoringPolicyCreate,
    MonitoringPolicyPreset,
    MonitoringPolicyRead,
    MonitoringPolicyUpdate,
)
from app.services.monitoring.policies import (
    POLICY_PRESETS,
    MonitoringPolicyRunner,
    ensure_default_policy_suite,
)

router = APIRouter()


def _to_model_data(body: MonitoringPolicyCreate | MonitoringPolicyUpdate) -> dict:
    data = body.model_dump(exclude_unset=isinstance(body, MonitoringPolicyUpdate))
    if "device_ids" in data and data["device_ids"] is not None:
        data["device_ids"] = [str(v) for v in data["device_ids"]]
    return data


async def _get_or_404(db: AsyncSession, policy_id: uuid.UUID) -> MonitoringPolicy:
    policy = await db.get(MonitoringPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Monitoring policy not found")
    return policy


@router.get("/presets", response_model=list[MonitoringPolicyPreset])
async def list_policy_presets() -> list[MonitoringPolicyPreset]:
    return [MonitoringPolicyPreset.model_validate(preset) for preset in POLICY_PRESETS]


@router.get("", response_model=list[MonitoringPolicyRead])
async def list_monitoring_policies(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = None,
    policy_type: str | None = None,
) -> list[MonitoringPolicyRead]:
    await ensure_default_policy_suite(async_session_factory)
    stmt = select(MonitoringPolicy)
    if enabled is not None:
        stmt = stmt.where(MonitoringPolicy.enabled == enabled)
    if policy_type:
        stmt = stmt.where(MonitoringPolicy.policy_type == policy_type)
    stmt = stmt.order_by(MonitoringPolicy.name.asc())
    result = await db.execute(stmt)
    return [MonitoringPolicyRead.model_validate(p) for p in result.scalars().all()]


@router.post("", response_model=MonitoringPolicyRead, status_code=status.HTTP_201_CREATED)
async def create_monitoring_policy(
    body: MonitoringPolicyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringPolicyRead:
    policy = MonitoringPolicy(**_to_model_data(body))
    db.add(policy)
    await db.flush()
    await db.refresh(policy)
    return MonitoringPolicyRead.model_validate(policy)


@router.get("/{id}", response_model=MonitoringPolicyRead)
async def get_monitoring_policy(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringPolicyRead:
    return MonitoringPolicyRead.model_validate(await _get_or_404(db, id))


@router.patch("/{id}", response_model=MonitoringPolicyRead)
async def update_monitoring_policy(
    id: uuid.UUID,
    body: MonitoringPolicyUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MonitoringPolicyRead:
    policy = await _get_or_404(db, id)
    for key, value in _to_model_data(body).items():
        setattr(policy, key, value)
    policy.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(policy)
    return MonitoringPolicyRead.model_validate(policy)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitoring_policy(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    policy = await _get_or_404(db, id)
    await db.delete(policy)


@router.post("/{id}/run", response_model=dict[str, int])
async def run_monitoring_policy(id: uuid.UUID) -> dict[str, int]:
    runner = MonitoringPolicyRunner(async_session_factory)
    return await runner.run_policy(id)
