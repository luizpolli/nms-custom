"""Network and per-service score history from persisted snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.assurance.schemas import NetworkScorePoint, ServiceScorePoint
from app.database import get_db
from app.models.service import Service, ServiceScoreSnapshot

router = APIRouter()


def _bucket_snapshots(
    snapshots: list[ServiceScoreSnapshot],
    since: datetime,
    bucket_minutes: int,
) -> list[NetworkScorePoint]:
    bucket_secs = bucket_minutes * 60
    since_ts = since.timestamp()
    buckets: dict[int, list[tuple[uuid.UUID, int]]] = {}
    for s in snapshots:
        ts = s.captured_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        offset = ts.timestamp() - since_ts
        key = int(offset // bucket_secs)
        buckets.setdefault(key, []).append((s.service_id, s.score))

    result: list[NetworkScorePoint] = []
    for key in sorted(buckets):
        entries = buckets[key]
        scores = [e[1] for e in entries]
        bucket_start = datetime.fromtimestamp(since_ts + key * bucket_secs, tz=UTC)
        result.append(
            NetworkScorePoint(
                bucket_start=bucket_start,
                avg_score=round(sum(scores) / len(scores), 2),
                min_score=int(min(scores)),
                max_score=int(max(scores)),
                sample_count=int(len(scores)),
                service_count=int(len({e[0] for e in entries})),
            )
        )
    return result


@router.get("/history", response_model=list[NetworkScorePoint])
async def assurance_network_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = 24,
    bucket_minutes: int = 15,
) -> list[NetworkScorePoint]:
    hours = max(1, min(hours, 720))
    bucket_minutes = max(1, min(bucket_minutes, 1440))
    since = datetime.now(UTC) - timedelta(hours=hours)

    result = await db.execute(
        select(ServiceScoreSnapshot)
        .where(ServiceScoreSnapshot.captured_at >= since)
        .order_by(ServiceScoreSnapshot.captured_at.asc())
    )
    snapshots = list(result.scalars().all())
    return _bucket_snapshots(snapshots, since, bucket_minutes)


@router.get("/services/{service_id}/history", response_model=list[ServiceScorePoint])
async def assurance_service_history(
    service_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    hours: int = 24,
    limit: int = 500,
) -> list[ServiceScorePoint]:
    """Return service score snapshots over the requested time window."""
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    hours = max(1, min(hours, 24 * 30))
    limit = max(1, min(limit, 5000))
    since = datetime.now(UTC) - timedelta(hours=hours)

    result = await db.execute(
        select(ServiceScoreSnapshot)
        .where(ServiceScoreSnapshot.service_id == service_id)
        .where(ServiceScoreSnapshot.captured_at >= since)
        .order_by(ServiceScoreSnapshot.captured_at.asc())
        .limit(limit)
    )
    snapshots = list(result.scalars().all())
    return [
        ServiceScorePoint(
            captured_at=s.captured_at,
            score=s.score,
            base_score=s.base_score,
            dependency_penalty=s.dependency_penalty,
            health_state=s.health_state,
            evidence=s.evidence,
        )
        for s in snapshots
    ]
