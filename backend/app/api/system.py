"""System health and NMS self-observability API routes."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.services.observability import get_all_worker_status

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
