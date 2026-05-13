"""API key authentication/authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass

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
    return Principal(subject="api-key", role="admin")
