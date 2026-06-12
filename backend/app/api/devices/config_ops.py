"""Config backup and drift endpoints — collect, list, diff, golden baseline."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.devices.common import _get_device_or_404, router
from app.api.devices.interface_ops import _is_ios_xr
from app.database import get_db
from app.models.config_backup import ConfigBackup
from app.security.audit import audit
from app.security.auth import (
    PERM_COMMANDS_READ,
    PERM_COMMANDS_RUN,
    Principal,
    require_command_permission,
    require_roles,
)
from app.services.config_drift import (
    config_hash,
    drift_summary,
    normalize_config,
    unified_config_diff,
)
from app.services.ssh.client import SSHClient
from app.services.ssh.command_runner import ssh_credential_for_device

_DIFF_MAX_BACKUPS = 200


class GoldenPromoteRequest(BaseModel):
    backup_id: uuid.UUID


def _backup_meta(backup: ConfigBackup) -> dict[str, object]:
    return {
        "id": str(backup.id),
        "kind": backup.kind,
        "contentHash": backup.content_hash,
        "sizeBytes": backup.size_bytes,
        "collectedBy": backup.collected_by,
        "createdAt": backup.created_at.isoformat() if backup.created_at else None,
    }


async def _latest_for_kind(db: AsyncSession, device_id: uuid.UUID, kind: str) -> ConfigBackup | None:
    stmt = (
        select(ConfigBackup)
        .where(ConfigBackup.device_id == device_id, ConfigBackup.kind == kind)
        .order_by(ConfigBackup.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _backup_or_404(
    db: AsyncSession, device_id: uuid.UUID, backup_id: uuid.UUID
) -> ConfigBackup:
    stmt = select(ConfigBackup).where(
        ConfigBackup.id == backup_id, ConfigBackup.device_id == device_id
    )
    result = await db.execute(stmt)
    backup = result.scalar_one_or_none()
    if backup is None:
        raise HTTPException(status_code=404, detail="Config backup not found for this device")
    return backup


# ---------------------------------------------------------------------------
# Collect / list / read
# ---------------------------------------------------------------------------


@router.post("/{id}/config-backups")
async def collect_config_backup(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_RUN))],
) -> dict[str, object]:
    """Fetch the running config over SSH and store it (deduplicated by hash)."""
    device = await _get_device_or_404(db, id)

    try:
        ssh_cred = ssh_credential_for_device(device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    device_type = "ios-xr" if _is_ios_xr(device) else "ios-xe"
    try:
        async with SSHClient(ssh_cred) as client:
            raw = await client.backup_config(device_type=device_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    normalized = normalize_config(raw)
    if not normalized:
        raise HTTPException(status_code=502, detail="Device returned an empty configuration")
    digest = config_hash(normalized)

    latest = await _latest_for_kind(db, id, "backup")
    if latest is not None and latest.content_hash == digest:
        audit("config.backup_collect", actor=principal.subject, target=str(id), deduplicated=True)
        return {**_backup_meta(latest), "deduplicated": True}

    backup = ConfigBackup(
        device_id=id,
        kind="backup",
        content=normalized,
        content_hash=digest,
        size_bytes=len(normalized.encode()),
        collected_by=principal.subject,
    )
    db.add(backup)
    await db.flush()
    audit("config.backup_collect", actor=principal.subject, target=str(id), deduplicated=False)
    return {**_backup_meta(backup), "deduplicated": False}


@router.get("/{id}/config-backups")
async def list_config_backups(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
    limit: int = Query(50, ge=1, le=_DIFF_MAX_BACKUPS),
) -> list[dict[str, object]]:
    await _get_device_or_404(db, id)
    stmt = (
        select(ConfigBackup)
        .where(ConfigBackup.device_id == id)
        .order_by(ConfigBackup.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_backup_meta(b) for b in result.scalars().all()]


@router.get("/{id}/config-backups/{backup_id}")
async def get_config_backup(
    id: uuid.UUID,
    backup_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
) -> dict[str, object]:
    await _get_device_or_404(db, id)
    backup = await _backup_or_404(db, id, backup_id)
    return {**_backup_meta(backup), "content": backup.content}


# ---------------------------------------------------------------------------
# Diff / golden / drift
# ---------------------------------------------------------------------------


@router.get("/{id}/config-backups/{backup_id}/diff")
async def diff_config_backup(
    id: uuid.UUID,
    backup_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
    against: str = Query("previous", description="'previous', 'golden', or a backup UUID"),
) -> dict[str, object]:
    """Diff *backup_id* against an older backup, the golden config, or a UUID."""
    await _get_device_or_404(db, id)
    backup = await _backup_or_404(db, id, backup_id)

    if against == "golden":
        base = await _latest_for_kind(db, id, "golden")
        if base is None:
            raise HTTPException(status_code=404, detail="No golden config set for this device")
    elif against == "previous":
        stmt = (
            select(ConfigBackup)
            .where(
                ConfigBackup.device_id == id,
                ConfigBackup.kind == "backup",
                ConfigBackup.created_at < backup.created_at,
            )
            .order_by(ConfigBackup.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        base = result.scalar_one_or_none()
        if base is None:
            raise HTTPException(status_code=404, detail="No earlier backup to diff against")
    else:
        try:
            base_id = uuid.UUID(against)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="against must be 'previous', 'golden', or a backup UUID"
            ) from exc
        base = await _backup_or_404(db, id, base_id)

    diff_text = unified_config_diff(
        base.content, backup.content, f"{base.kind}:{base.id}", f"{backup.kind}:{backup.id}"
    )
    return {
        "baseId": str(base.id),
        "backupId": str(backup.id),
        "identical": not diff_text,
        "diff": diff_text,
        **drift_summary(diff_text),
    }


@router.post("/{id}/golden-config")
async def promote_golden_config(
    id: uuid.UUID,
    body: GoldenPromoteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_roles("root", "admin"))],
) -> dict[str, object]:
    """Promote an existing backup to be the device's golden (baseline) config."""
    await _get_device_or_404(db, id)
    backup = await _backup_or_404(db, id, body.backup_id)

    golden = ConfigBackup(
        device_id=id,
        kind="golden",
        content=backup.content,
        content_hash=backup.content_hash,
        size_bytes=backup.size_bytes,
        collected_by=principal.subject,
    )
    db.add(golden)
    await db.flush()
    audit(
        "config.golden_promote",
        actor=principal.subject,
        target=str(id),
        role=principal.role,
        source_backup=str(backup.id),
    )
    return _backup_meta(golden)


@router.get("/{id}/config-drift")
async def get_config_drift(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_READ))],
) -> dict[str, object]:
    """Compare the latest backup against the golden config."""
    await _get_device_or_404(db, id)
    golden = await _latest_for_kind(db, id, "golden")
    backup = await _latest_for_kind(db, id, "backup")

    if golden is None or backup is None:
        return {
            "status": "no_golden" if golden is None else "no_backup",
            "goldenId": str(golden.id) if golden else None,
            "backupId": str(backup.id) if backup else None,
            "diff": "",
            "added": 0,
            "removed": 0,
        }

    diff_text = unified_config_diff(
        golden.content, backup.content, f"golden:{golden.id}", f"backup:{backup.id}"
    )
    return {
        "status": "in_sync" if not diff_text else "drift",
        "goldenId": str(golden.id),
        "backupId": str(backup.id),
        "diff": diff_text,
        **drift_summary(diff_text),
    }
