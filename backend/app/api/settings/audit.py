"""Settings audit + account audit endpoints (list / export / paths)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogRead
from app.security.auth import (
    PERM_SETTINGS_AUDIT_TRAILS,
    PERM_SETTINGS_VIEW_AUDIT,
    require_settings_permission,
)

from ._schemas import (
    ACCOUNT_AUDIT_EXPORT_COLUMNS,
    AccountAuditPaths,
    _account_audit_stmt,
    _audit_csv_value,
)

router = APIRouter()


@router.get("/audit", response_model=list[AuditLogRead])
async def list_settings_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS)),
    ],
    limit: int = 50,
) -> list[AuditLogRead]:
    capped_limit = min(max(limit, 1), 200)
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.object_type == "settings")
        .order_by(AuditLog.timestamp.desc())
        .limit(capped_limit)
    )
    return [AuditLogRead.model_validate(row) for row in result.scalars().all()]


@router.get("/account-audit", response_model=list[AuditLogRead])
async def list_account_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS)),
    ],
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    role: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogRead]:
    capped_limit = min(max(limit, 1), 500)
    result = await db.execute(
        _account_audit_stmt(
            actor=actor,
            action=action,
            outcome=outcome,
            role=role,
            q=q,
            since=since,
            until=until,
        )
        .order_by(AuditLog.timestamp.desc())
        .offset(max(offset, 0))
        .limit(capped_limit)
    )
    return [AuditLogRead.model_validate(row) for row in result.scalars().all()]


@router.get("/account-audit/export")
async def export_account_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS)),
    ],
    export_format: str = Query("csv", alias="format", pattern="^csv$"),
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    role: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    del export_format
    result = await db.execute(
        _account_audit_stmt(
            actor=actor,
            action=action,
            outcome=outcome,
            role=role,
            q=q,
            since=since,
            until=until,
        ).order_by(AuditLog.timestamp.desc())
    )
    entries = result.scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ACCOUNT_AUDIT_EXPORT_COLUMNS)
    writer.writeheader()
    for entry in entries:
        details = entry.details or {}
        writer.writerow(
            {
                "Timestamp": _audit_csv_value(entry.timestamp),
                "Actor": _audit_csv_value(entry.actor),
                "Role": _audit_csv_value(details.get("role")),
                "Action": _audit_csv_value(entry.action),
                "Outcome": _audit_csv_value(entry.outcome),
                "Source IP": _audit_csv_value(entry.source_ip),
                "Message": _audit_csv_value(entry.message),
                "Path": _audit_csv_value(details.get("path")),
                "Method": _audit_csv_value(details.get("method")),
                "Status Code": _audit_csv_value(details.get("status_code")),
            }
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="account_audit_export.csv"'},
    )


@router.get("/account-audit/paths", response_model=AccountAuditPaths)
async def get_account_audit_paths(
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS)),
    ],
) -> AccountAuditPaths:
    return AccountAuditPaths(
        user_activity_path=settings.account_audit_log_path,
        privileged_activity_path=settings.privileged_account_audit_log_path,
    )
