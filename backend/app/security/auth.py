"""API key authentication/authorization dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str = "admin"


def _configured_keys() -> set[str]:
    raw = settings.api_keys
    if isinstance(raw, str):
        return {item.strip() for item in raw.split(",") if item.strip()}
    return {str(item).strip() for item in raw if str(item).strip()}


async def require_api_auth(
    request: Request,
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> Principal:
    """Require X-API-Key or Authorization: Bearer when API auth is enabled.

    Auth is off by default for local development/tests. Set API_AUTH_ENABLED=true
    and API_KEYS=<comma-separated keys> in deployed environments.
    """
    if not settings.api_auth_enabled:
        return Principal(subject="local-dev")

    allowed = _configured_keys()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is enabled but no API_KEYS are configured",
        )

    presented = request.headers.get("x-api-key")
    if not presented and bearer:
        presented = bearer.credentials
    if not presented or presented not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Principal(subject="api-key", role="admin")
