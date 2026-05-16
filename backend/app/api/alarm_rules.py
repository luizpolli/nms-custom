"""Alarm customization rule API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alarm_rule import AlarmRule
from app.schemas.alarm_rule import AlarmRuleCreate, AlarmRuleRead, AlarmRuleUpdate

router = APIRouter()


async def _get_or_404(db: AsyncSession, rule_id: uuid.UUID) -> AlarmRule:
    result = await db.execute(select(AlarmRule).where(AlarmRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Alarm rule not found")
    return rule


@router.get("", response_model=list[AlarmRuleRead])
async def list_alarm_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = None,
    source_type: str | None = None,
) -> list[AlarmRuleRead]:
    stmt = select(AlarmRule)
    if enabled is not None:
        stmt = stmt.where(AlarmRule.enabled == enabled)
    if source_type:
        stmt = stmt.where(AlarmRule.source_type == source_type)
    stmt = stmt.order_by(AlarmRule.priority.asc(), AlarmRule.created_at.asc())
    result = await db.execute(stmt)
    return [AlarmRuleRead.model_validate(rule) for rule in result.scalars().all()]


@router.post("", response_model=AlarmRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alarm_rule(
    body: AlarmRuleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRuleRead:
    rule = AlarmRule(**body.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return AlarmRuleRead.model_validate(rule)


@router.get("/{id}", response_model=AlarmRuleRead)
async def get_alarm_rule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRuleRead:
    rule = await _get_or_404(db, id)
    return AlarmRuleRead.model_validate(rule)


@router.patch("/{id}", response_model=AlarmRuleRead)
async def update_alarm_rule(
    id: uuid.UUID,
    body: AlarmRuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmRuleRead:
    rule = await _get_or_404(db, id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    rule.updated_at = datetime.now()
    await db.flush()
    await db.refresh(rule)
    return AlarmRuleRead.model_validate(rule)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alarm_rule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    rule = await _get_or_404(db, id)
    await db.delete(rule)
