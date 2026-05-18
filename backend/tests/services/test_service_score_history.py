"""Tests for service score history persistence and history endpoint behavior."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.assurance import (
    ServiceImpact,
    _persist_service_score_snapshots,
)
from app.models.service import Service, ServiceScoreSnapshot


async def _make_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Only create the tables this test needs; many production tables use
    # PostgreSQL-specific types (ARRAY, JSONB) that SQLite cannot compile.
    async with engine.begin() as conn:
        await conn.run_sync(Service.__table__.create)
        await conn.run_sync(ServiceScoreSnapshot.__table__.create)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return sessionmaker()


def _impact(service_id: uuid.UUID, score: int = 80) -> ServiceImpact:
    return ServiceImpact(
        service_id=service_id,
        name="svc",
        kind="customer",
        score=score,
        base_score=score,
        dependency_penalty=0,
        health_state="healthy" if score >= 90 else "degraded",
        member_count=1,
        impacted_member_count=0,
        active_alarm_count=0,
        worst_severity="info",
    )


@pytest.mark.asyncio
async def test_persist_snapshot_writes_first_sample():
    session = await _make_session()
    try:
        service = Service(id=uuid.uuid4(), name="svc-a", kind="customer")
        session.add(service)
        await session.commit()

        await _persist_service_score_snapshots(session, [_impact(service.id, 75)])

        rows = (await session.execute(select(ServiceScoreSnapshot))).scalars().all()
        assert len(rows) == 1
        assert rows[0].service_id == service.id
        assert rows[0].score == 75
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_persist_snapshot_throttles_recent_samples():
    session = await _make_session()
    try:
        service = Service(id=uuid.uuid4(), name="svc-b", kind="customer")
        session.add(service)
        await session.commit()

        await _persist_service_score_snapshots(session, [_impact(service.id, 80)])
        await _persist_service_score_snapshots(session, [_impact(service.id, 60)])

        rows = (await session.execute(select(ServiceScoreSnapshot))).scalars().all()
        assert len(rows) == 1, "second call within throttle window should be skipped"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_persist_snapshot_records_again_after_throttle():
    session = await _make_session()
    try:
        service = Service(id=uuid.uuid4(), name="svc-c", kind="customer")
        session.add(service)
        await session.commit()

        await _persist_service_score_snapshots(session, [_impact(service.id, 90)])

        stale = (await session.execute(select(ServiceScoreSnapshot))).scalars().one()
        stale.captured_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        await session.commit()

        await _persist_service_score_snapshots(session, [_impact(service.id, 55)])

        rows = (await session.execute(select(ServiceScoreSnapshot))).scalars().all()
        assert len(rows) == 2
        scores = sorted(r.score for r in rows)
        assert scores == [55, 90]
    finally:
        await session.close()
