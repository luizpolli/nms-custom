"""Helpers to redact secrets from logs and error surfaces."""

from __future__ import annotations

import re
from typing import Any

_SECRET_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "community",
    "read_community",
    "write_community",
    "auth_key",
    "enc_key",
    "private_key",
    "snmp_v3_auth_password",
    "snmp_v3_priv_password",
}

_KEY_VALUE_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|community|auth_key|enc_key|private_key)"
    r"\s*[:=]\s*([^\s,;]+)"
)


def redact(value: Any) -> Any:
    """Recursively redact common credential fields."""
    if isinstance(value, dict):
        return {
            k: "***REDACTED***" if str(k).lower() in _SECRET_KEYS else redact(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    if isinstance(value, str):
        return _KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}=***REDACTED***", value)
    return value


def configure_log_redaction() -> None:
    """Install a Loguru patcher that redacts formatted messages."""
    from loguru import logger

    def _patch(record: dict) -> None:
        record["message"] = str(redact(record.get("message", "")))

    logger.configure(patcher=_patch)  # type: ignore[arg-type]  # dict[Any,Any] is compatible with Record at runtime
