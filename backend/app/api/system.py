"""System health and NMS self-observability API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.observability import get_all_worker_status
from app.services.retention import DEFAULT_RETENTION_POLICIES, ensure_timescale_schema

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/health")
async def system_health() -> dict:
    """Return best-effort internal health for separated workers/receivers.

    Worker heartbeat collection is intentionally best-effort: Redis outages or
    missing heartbeat keys should show up as stale worker state, not break the
    system-health endpoint itself.
    """
    workers = await get_all_worker_status()
    stale_workers = [worker.kind for worker in workers if worker.is_stale]

    return {
        "ok": not stale_workers,
        "generated_at": _now_iso(),
        "workers": [worker.to_dict() for worker in workers],
        "summary": {
            "worker_count": len(workers),
            "stale_count": len(stale_workers),
            "stale_workers": stale_workers,
        },
    }


@router.get("/retention")
async def retention_status(db: Annotated[AsyncSession, Depends(get_db)]) -> dict:
    """Return configured retention windows and best-effort Timescale setup status."""
    timescale = await ensure_timescale_schema(db)
    return {
        "generated_at": _now_iso(),
        "policies": [
            {"table": policy.table, "timestamp_column": policy.timestamp_column, "keep_days": policy.keep_days}
            for policy in DEFAULT_RETENTION_POLICIES
        ],
        "timescale": timescale,
    }
