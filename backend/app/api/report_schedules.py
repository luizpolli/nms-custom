"""Scheduled reports API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.report_schedule import GeneratedReport, ReportSchedule
from app.schemas.report_schedule import (
    GeneratedReportRead,
    ReportScheduleCreate,
    ReportScheduleRead,
    ReportScheduleUpdate,
)
from app.services.reports.scheduler import ReportScheduleRunner

router = APIRouter()


async def _get_or_404(db: AsyncSession, schedule_id: uuid.UUID) -> ReportSchedule:
    result = await db.execute(select(ReportSchedule).where(ReportSchedule.id == schedule_id))
    schedule = result.scalar_one_or_none()
    if schedule is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return schedule


@router.get("", response_model=list[ReportScheduleRead])
async def list_schedules(
    db: Annotated[AsyncSession, Depends(get_db)],
    enabled: bool | None = None,
) -> list[ReportScheduleRead]:
    stmt = select(ReportSchedule)
    if enabled is not None:
        stmt = stmt.where(ReportSchedule.enabled == enabled)
    stmt = stmt.order_by(ReportSchedule.created_at.asc())
    result = await db.execute(stmt)
    return [ReportScheduleRead.model_validate(s) for s in result.scalars().all()]


@router.post("", response_model=ReportScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ReportScheduleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportScheduleRead:
    schedule = ReportSchedule(**body.model_dump())
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return ReportScheduleRead.model_validate(schedule)


@router.get("/{id}", response_model=ReportScheduleRead)
async def get_schedule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportScheduleRead:
    schedule = await _get_or_404(db, id)
    return ReportScheduleRead.model_validate(schedule)


@router.patch("/{id}", response_model=ReportScheduleRead)
async def update_schedule(
    id: uuid.UUID,
    body: ReportScheduleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReportScheduleRead:
    schedule = await _get_or_404(db, id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(schedule, key, value)
    schedule.updated_at = datetime.now()
    await db.flush()
    await db.refresh(schedule)
    return ReportScheduleRead.model_validate(schedule)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    schedule = await _get_or_404(db, id)
    await db.delete(schedule)


@router.post("/{id}/run", response_model=GeneratedReportRead)
async def run_now(id: uuid.UUID) -> GeneratedReportRead:
    runner = ReportScheduleRunner(async_session_factory)
    artefact = await runner.run_schedule(id)
    if artefact is None:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return GeneratedReportRead.model_validate(artefact)


@router.get("/{id}/runs", response_model=list[GeneratedReportRead])
async def list_runs(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 25,
) -> list[GeneratedReportRead]:
    stmt = (
        select(GeneratedReport)
        .where(GeneratedReport.schedule_id == id)
        .order_by(GeneratedReport.generated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [GeneratedReportRead.model_validate(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}/download")
async def download_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == run_id))
    artefact = result.scalar_one_or_none()
    if artefact is None:
        raise HTTPException(status_code=404, detail="Generated report not found")
    return StreamingResponse(
        iter([artefact.content or b""]),
        media_type=artefact.content_type,
        headers={"Content-Disposition": f"attachment; filename={artefact.filename}"},
    )
