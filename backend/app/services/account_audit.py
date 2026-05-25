"""Account activity audit helpers for GUI and CLI-visible trails."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audit import AuditLog
from app.models.forwarding import ForwardingTarget
from app.security.auth import Principal
from app.security.redaction import redact
from app.services.forwarding.engine import ForwardingEngine

ACCOUNT_AUDIT_OBJECT_TYPE = "account_audit"
PRIVILEGED_ROLES = {"admin", "root"}
FORWARDABLE_ACCOUNT_ACTIONS = {"auth.login", "auth.logout", "user.privileges.update"}


def is_privileged(principal: Principal) -> bool:
    return principal.role.lower() in PRIVILEGED_ROLES


def _role_is_privileged(role: str | None) -> bool:
    if not role:
        return False
    roles = [part.strip().lower() for part in role.split(",") if part.strip()]
    return any(role_name in PRIVILEGED_ROLES for role_name in roles)


def account_audit_path(principal: Principal) -> str:
    if is_privileged(principal):
        return settings.privileged_account_audit_log_path
    return settings.account_audit_log_path


def _write_jsonl(path: str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(payload), default=str, sort_keys=True))
        handle.write("\n")


async def _forward_sensitive_account_event(db: AsyncSession, payload: dict[str, Any]) -> None:
    if payload["action"] not in FORWARDABLE_ACCOUNT_ACTIONS:
        return
    details = payload.get("details") or {}
    subject_role = str(details.get("target_role") or payload.get("role") or "")
    if _role_is_privileged(subject_role):
        return

    event = {
        "event_type": ACCOUNT_AUDIT_OBJECT_TYPE,
        "severity": "warning" if payload["action"] != "auth.logout" else "info",
        "source": "nms-custom",
        "timestamp": payload["timestamp"],
        "message": payload.get("message") or payload["action"],
        "actor": payload["actor"],
        "subject": payload["subject"],
        "role": payload["role"],
        "action": payload["action"],
        "outcome": payload["outcome"],
        "source_ip": payload.get("source_ip"),
        "details": redact(details),
    }
    result = await db.execute(select(ForwardingTarget).where(ForwardingTarget.enabled.is_(True)))
    targets = [
        target for target in result.scalars().all()
        if ACCOUNT_AUDIT_OBJECT_TYPE in (target.event_types or [])
    ]
    for target in targets:
        try:
            await ForwardingEngine.send_to_target(target, event, timeout_seconds=3.0)
        except Exception:
            # The account audit record must not fail because an external collector is down.
            continue


async def record_account_activity(
    db: AsyncSession,
    *,
    principal: Principal,
    action: str,
    source_ip: str | None = None,
    outcome: str = "success",
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Persist account activity to DB and the CLI-friendly JSONL path."""
    now = datetime.now(timezone.utc)
    role = principal.role.lower()
    path = account_audit_path(principal)
    actor = f"{principal.subject}:{role}"
    payload = {
        "timestamp": now.isoformat(),
        "actor": actor,
        "subject": principal.subject,
        "role": role,
        "action": action,
        "outcome": outcome,
        "source_ip": source_ip,
        "message": message,
        "details": details or {},
        "audit_path": path,
    }
    _write_jsonl(path, payload)
    db.add(
        AuditLog(
            timestamp=now,
            actor=actor,
            action=action,
            object_type=ACCOUNT_AUDIT_OBJECT_TYPE,
            object_id=principal.subject,
            outcome=outcome,
            source_ip=source_ip,
            message=message,
            details={
                "role": role,
                "audit_path": path,
                **(details or {}),
            },
        )
    )
    await _forward_sensitive_account_event(db, payload)
