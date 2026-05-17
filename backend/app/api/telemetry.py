"""Telemetry MVP API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.telemetry import TelemetryCollector, TelemetrySensorPath, TelemetrySubscription
from app.schemas.telemetry import (
    TelemetryCollectorCreate,
    TelemetryCollectorRead,
    TelemetryHealth,
    TelemetryIngestResult,
    TelemetrySampleIngest,
    TelemetrySensorPathCreate,
    TelemetrySensorPathRead,
    TelemetrySubscriptionCreate,
    TelemetrySubscriptionRead,
)
from app.services.telemetry import TelemetryIngestionService

router = APIRouter()


@router.get("/collectors", response_model=list[TelemetryCollectorRead])
async def list_collectors(db: Annotated[AsyncSession, Depends(get_db)]) -> list[TelemetryCollectorRead]:
    rows = (await db.execute(select(TelemetryCollector).order_by(TelemetryCollector.name))).scalars().all()
    return [TelemetryCollectorRead.model_validate(row) for row in rows]


@router.post("/collectors", response_model=TelemetryCollectorRead, status_code=status.HTTP_201_CREATED)
async def create_collector(
    body: TelemetryCollectorCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelemetryCollectorRead:
    row = TelemetryCollector(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return TelemetryCollectorRead.model_validate(row)


@router.get("/sensor-paths", response_model=list[TelemetrySensorPathRead])
async def list_sensor_paths(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = Query(None),
) -> list[TelemetrySensorPathRead]:
    stmt = select(TelemetrySensorPath).order_by(TelemetrySensorPath.path)
    if enabled is not None:
        stmt = stmt.where(TelemetrySensorPath.enabled.is_(enabled))
    rows = (await db.execute(stmt)).scalars().all()
    return [TelemetrySensorPathRead.model_validate(row) for row in rows]


@router.post("/sensor-paths", response_model=TelemetrySensorPathRead, status_code=status.HTTP_201_CREATED)
async def create_sensor_path(
    body: TelemetrySensorPathCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelemetrySensorPathRead:
    row = TelemetrySensorPath(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return TelemetrySensorPathRead.model_validate(row)


@router.get("/subscriptions", response_model=list[TelemetrySubscriptionRead])
async def list_subscriptions(db: Annotated[AsyncSession, Depends(get_db)]) -> list[TelemetrySubscriptionRead]:
    rows = (await db.execute(select(TelemetrySubscription).order_by(TelemetrySubscription.name))).scalars().all()
    return [TelemetrySubscriptionRead.model_validate(row) for row in rows]


@router.post("/subscriptions", response_model=TelemetrySubscriptionRead, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    body: TelemetrySubscriptionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelemetrySubscriptionRead:
    row = TelemetrySubscription(**body.model_dump())
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return TelemetrySubscriptionRead.model_validate(row)


@router.post("/samples", response_model=TelemetryIngestResult, status_code=status.HTTP_202_ACCEPTED)
async def ingest_sample(body: TelemetrySampleIngest) -> TelemetryIngestResult:
    return await TelemetryIngestionService(async_session_factory).ingest_sample(body)


@router.get("/health", response_model=TelemetryHealth)
async def telemetry_health(db: Annotated[AsyncSession, Depends(get_db)]) -> TelemetryHealth:
    collectors = (await db.execute(select(func.count()).select_from(TelemetryCollector))).scalar_one()
    enabled_collectors = (
        await db.execute(select(func.count()).select_from(TelemetryCollector).where(TelemetryCollector.enabled.is_(True)))
    ).scalar_one()
    subscriptions = (await db.execute(select(func.count()).select_from(TelemetrySubscription))).scalar_one()
    enabled_subscriptions = (
        await db.execute(select(func.count()).select_from(TelemetrySubscription).where(TelemetrySubscription.enabled.is_(True)))
    ).scalar_one()
    return TelemetryHealth(
        collectors=collectors,
        enabled_collectors=enabled_collectors,
        subscriptions=subscriptions,
        enabled_subscriptions=enabled_subscriptions,
    )
