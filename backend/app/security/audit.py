"""Minimal audit logging for sensitive actions."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.security.redaction import redact


def audit(action: str, *, actor: str = "system", target: str | None = None, **details: Any) -> None:
    """Emit a structured audit event with secrets redacted."""
    logger.bind(audit=True).info(
        "audit action={} actor={} target={} details={}",
        action,
        actor,
        target or "-",
        redact(details),
    )
