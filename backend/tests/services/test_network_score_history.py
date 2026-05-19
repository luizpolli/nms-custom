"""Tests for the network-wide score history bucketing endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.assurance import NetworkScorePoint, _bucket_snapshots
from app.models.service import Service, ServiceScoreSnapshot


async def _make_session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Service.__table__.create)
        await conn.run_sync(ServiceScoreSnapshot.__table__.create)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return sessionmaker()


def _snap(service_id: uuid.UUID, score: int, captured_at: datetime) -> ServiceScoreSnapshot:
    s = ServiceScoreSnapshot(
        service_id=service_id,
        score=score,
        base_score=score,
        dependency_penalty=0,
        health_state="healthy" if score >= 90 else "degraded",
    )
    s.captured_at = captured_at
    return s


@pytest.mark.asyncio
async def test_empty_returns_no_buckets():
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    result = _bucket_snapshots([], since, bucket_minutes=15)
    assert result == []


@pytest.mark.asyncio
async def test_single_snapshot_single_bucket():
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    svc = uuid.uuid4()
    snap = _snap(svc, 80, since + timedelta(minutes=5))
    result = _bucket_snapshots([snap], since, bucket_minutes=15)
    assert len(result) == 1
    point = result[0]
    assert isinstance(point, NetworkScorePoint)
    assert point.avg_score == 80.0
    assert point.min_score == 80
    assert point.max_score == 80
    assert point.sample_count == 1
    assert point.service_count == 1


@pytest.mark.asyncio
async def test_multi_bucket_aggregation():
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    svc1, svc2 = uuid.uuid4(), uuid.uuid4()
    snaps = [
        _snap(svc1, 90, since + timedelta(minutes=2)),
        _snap(svc2, 70, since + timedelta(minutes=4)),
        _snap(svc1, 60, since + timedelta(minutes=20)),
    ]
    result = _bucket_snapshots(snaps, since, bucket_minutes=15)
    assert len(result) == 2

    bucket0 = result[0]
    assert bucket0.sample_count == 2
    assert bucket0.service_count == 2
    assert bucket0.min_score == 70
    assert bucket0.max_score == 90
    assert bucket0.avg_score == 80.0

    bucket1 = result[1]
    assert bucket1.sample_count == 1
    assert bucket1.service_count == 1
    assert bucket1.min_score == 60
    assert bucket1.max_score == 60


@pytest.mark.asyncio
async def test_naive_datetime_treated_as_utc():
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    svc = uuid.uuid4()
    naive_ts = (since + timedelta(minutes=3)).replace(tzinfo=None)
    snap = _snap(svc, 55, naive_ts)
    result = _bucket_snapshots([snap], since, bucket_minutes=15)
    assert len(result) == 1
    assert result[0].min_score == 55


@pytest.mark.asyncio
async def test_buckets_sorted_ascending():
    since = datetime.now(timezone.utc) - timedelta(hours=2)
    svc = uuid.uuid4()
    snaps = [
        _snap(svc, 80, since + timedelta(minutes=100)),
        _snap(svc, 90, since + timedelta(minutes=10)),
        _snap(svc, 75, since + timedelta(minutes=50)),
    ]
    result = _bucket_snapshots(snaps, since, bucket_minutes=30)
    starts = [r.bucket_start for r in result]
    assert starts == sorted(starts)


@pytest.mark.asyncio
async def test_avg_score_precision():
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    svc = uuid.uuid4()
    snaps = [
        _snap(svc, 85, since + timedelta(minutes=1)),
        _snap(svc, 86, since + timedelta(minutes=2)),
        _snap(svc, 87, since + timedelta(minutes=3)),
    ]
    result = _bucket_snapshots(snaps, since, bucket_minutes=15)
    assert len(result) == 1
    assert result[0].avg_score == round((85 + 86 + 87) / 3, 2)
    assert result[0].min_score == 85
    assert result[0].max_score == 87
    assert result[0].sample_count == 3
