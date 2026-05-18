"""API key authentication/authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import HTTPException, status
from starlette.requests import HTTPConnection

from app.config import settings


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str = "admin"


def _configured_keys() -> set[str]:
    raw = settings.api_keys
    if isinstance(raw, str):
        return {item.strip() for item in raw.split(",") if item.strip()}
    return {str(item).strip() for item in raw if str(item).strip()}


def _role_map() -> dict[str, str]:
    raw = getattr(settings, "api_key_roles", "") or ""
    out: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        key, role = entry.split(":", 1)
        key = key.strip()
        role = role.strip().lower()
        if key and role:
            out[key] = role
    return out


def require_roles(*roles: str):
    """FastAPI dependency factory: require the principal to hold any of `roles`.

    When API auth is disabled the local-dev principal is granted implicitly.
    """
    allowed: frozenset[str] = frozenset(r.strip().lower() for r in roles if r)

    async def _checker(conn: HTTPConnection) -> Principal:
        principal = await require_api_auth(conn)
        if not allowed:
            return principal
        if principal.role.lower() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{principal.role}' is not permitted for this endpoint",
            )
        return principal

    return _checker


def roles_from_setting(value: str | Iterable[str]) -> tuple[str, ...]:
    """Parse a comma-separated role list from settings."""
    if isinstance(value, str):
        items = [r.strip().lower() for r in value.split(",") if r.strip()]
    else:
        items = [str(r).strip().lower() for r in value if str(r).strip()]
    return tuple(items)


async def require_api_auth(conn: HTTPConnection) -> Principal:
    """Require X-API-Key or Authorization: Bearer when API auth is enabled.

    Works for both HTTP routes and WebSocket endpoints because router-level
    dependencies are shared by FastAPI across both connection types.
    """
    if not settings.api_auth_enabled:
        return Principal(subject="local-dev")

    allowed = _configured_keys()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is enabled but no API_KEYS are configured",
        )

    presented = conn.headers.get("x-api-key")
    auth_header = conn.headers.get("authorization", "")
    if not presented and auth_header.lower().startswith("bearer "):
        presented = auth_header[7:].strip()
    if not presented or presented not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    role = _role_map().get(presented, "admin")
    return Principal(subject="api-key", role=role)
