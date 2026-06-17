"""System health, container management, and backup jobs API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import system_admin
from app.services.observability import get_all_worker_status
from app.services.retention import DEFAULT_RETENTION_POLICIES, ensure_timescale_schema

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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


class BackupConfigUpdate(BaseModel):
    enabled: bool | None = None
    schedule: str | None = None
    destination: str | None = None
    dest_path: str | None = None
    skip_redis: bool | None = None
    include_volumes: bool | None = None
    retain_days: int | None = None


class BackupTrigger(BaseModel):
    skip_redis: bool = False
    include_volumes: bool = False


@router.get("/containers")
async def list_containers() -> dict:
    """Return status of all known NMS containers via Docker CLI."""
    return await system_admin.get_container_statuses()


@router.post("/containers/{name}/restart")
async def restart_container(name: str) -> dict:
    """Restart a named container. Requires Docker socket to be mounted."""
    result = await system_admin.restart_container(name)
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result.get("error", "Restart failed"))
    return result


@router.get("/backups")
async def list_backups() -> list[dict]:
    """List backup directories produced by scripts/backup.sh."""
    return system_admin.list_backups()


@router.post("/backups", status_code=202)
async def trigger_backup(body: BackupTrigger) -> dict:
    """Trigger a backup job (runs scripts/backup.sh asynchronously)."""
    result = await system_admin.trigger_backup(
        skip_redis=body.skip_redis,
        include_volumes=body.include_volumes,
    )
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result.get("error", "Backup failed"))
    return result


@router.delete("/backups/{name}", status_code=204)
async def delete_backup(name: str) -> None:
    """Delete a named backup directory."""
    result = system_admin.delete_backup(name)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))


@router.get("/backup-config")
async def get_backup_config() -> dict:
    """Return current backup configuration."""
    return system_admin.get_backup_config()


@router.put("/backup-config")
async def update_backup_config(body: BackupConfigUpdate) -> dict:
    """Persist backup configuration."""
    current = system_admin.get_backup_config()
    update = body.model_dump(exclude_unset=True)
    current.update(update)
    return system_admin.save_backup_config(current)


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
