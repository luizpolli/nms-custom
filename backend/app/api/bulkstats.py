"""Bulkstats counter catalog + ingestion health API.

The catalog decides which (group, field_name) StarOS counters get promoted
into the shared kpis table during ingestion (see app/services/bulkstats/
ingest.py) — everything else still lands in bulkstats_raw_samples but isn't
chartable via the existing /api/performance KPI endpoints. Ingestion stats
expose per-source-ip health (unmatched devices, parse error counts) so an
admin can tell whether a configured watch/pull path is actually working.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bulkstats import BulkstatsCounterCatalog, BulkstatsIngestionStat
from app.schemas.bulkstats import (
    BulkstatsCounterCatalogCreate,
    BulkstatsCounterCatalogRead,
    BulkstatsCounterCatalogUpdate,
    BulkstatsIngestionStatRead,
)

router = APIRouter()


@router.get("/catalog", response_model=list[BulkstatsCounterCatalogRead])
async def list_catalog(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = Query(None),
    group: str | None = Query(None),
) -> list[BulkstatsCounterCatalogRead]:
    stmt = select(BulkstatsCounterCatalog).order_by(BulkstatsCounterCatalog.group, BulkstatsCounterCatalog.field_name)
    if enabled is not None:
        stmt = stmt.where(BulkstatsCounterCatalog.enabled.is_(enabled))
    if group:
        stmt = stmt.where(BulkstatsCounterCatalog.group == group)
    rows = (await db.execute(stmt)).scalars().all()
    return [BulkstatsCounterCatalogRead.model_validate(row) for row in rows]


@router.post("/catalog", response_model=BulkstatsCounterCatalogRead, status_code=status.HTTP_201_CREATED)
async def create_catalog_entry(
    body: BulkstatsCounterCatalogCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkstatsCounterCatalogRead:
    row = BulkstatsCounterCatalog(**body.model_dump())
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A catalog entry for group={body.group!r} field_name={body.field_name!r} already exists",
        ) from exc
    await db.refresh(row)
    return BulkstatsCounterCatalogRead.model_validate(row)


@router.patch("/catalog/{catalog_id}", response_model=BulkstatsCounterCatalogRead)
async def update_catalog_entry(
    catalog_id: uuid.UUID,
    body: BulkstatsCounterCatalogUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkstatsCounterCatalogRead:
    row = await db.get(BulkstatsCounterCatalog, catalog_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog entry not found")
    row.enabled = body.enabled
    await db.flush()
    await db.refresh(row)
    return BulkstatsCounterCatalogRead.model_validate(row)


@router.get("/ingestion-stats", response_model=list[BulkstatsIngestionStatRead])
async def list_ingestion_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[BulkstatsIngestionStatRead]:
    stmt = select(BulkstatsIngestionStat).order_by(BulkstatsIngestionStat.updated_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [BulkstatsIngestionStatRead.model_validate(row) for row in rows]
