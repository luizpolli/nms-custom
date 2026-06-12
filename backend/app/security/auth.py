"""API key authentication/authorization dependencies."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import HTTPException, status
from starlette.requests import HTTPConnection

from app.config import settings

# ---------------------------------------------------------------------------
# Fine-grained command permission constants
# ---------------------------------------------------------------------------

PERM_COMMANDS_READ = "commands:read"
PERM_COMMANDS_CREATE = "commands:create"
PERM_COMMANDS_UPDATE = "commands:update"
PERM_COMMANDS_DELETE = "commands:delete"
PERM_COMMANDS_RUN = "commands:run"
PERM_COMMANDS_RUN_BULK = "commands:run_bulk"
PERM_COMMANDS_EXPORT = "commands:export"
PERM_COMMANDS_SCHEDULE = "commands:schedule"

# Interface administrative control (shutdown / no shutdown). Deliberately
# restricted to root/admin — operators can run read commands but must not
# change port admin state.
PERM_INTERFACES_ADMIN = "interfaces:admin_status"

# Settings/admin permissions use the same catalog keys exposed by
# app.api.permissions_catalog so API-key roles and the UI speak one language.
PERM_SETTINGS_SYSTEM = "administrative_operations_system_settings"
PERM_SETTINGS_USERS_GROUPS = "administrative_operations_users_and_groups"
PERM_SETTINGS_USER_ADMIN_USERS_GROUPS = "user_administration_users_and_groups"
PERM_SETTINGS_VIEW_AUDIT = "administrative_operations_view_audit_logs_access"
PERM_SETTINGS_AUDIT_TRAILS = "administrative_operations_audit_trails"
PERM_SETTINGS_NETWORK_SNMP = "system_settings_submenu_network_and_device_snmp"
PERM_SETTINGS_ALARMS_EVENTS = "system_settings_submenu_alarm_and_events_alarm_and_events"

# Roles and their granted command permissions (additive).
_ROLE_COMMAND_PERMS: dict[str, frozenset[str]] = {
    "root": frozenset({
        PERM_COMMANDS_READ, PERM_COMMANDS_CREATE, PERM_COMMANDS_UPDATE,
        PERM_COMMANDS_DELETE, PERM_COMMANDS_RUN, PERM_COMMANDS_RUN_BULK,
        PERM_COMMANDS_EXPORT, PERM_COMMANDS_SCHEDULE, PERM_INTERFACES_ADMIN,
    }),
    "admin": frozenset({
        PERM_COMMANDS_READ, PERM_COMMANDS_CREATE, PERM_COMMANDS_UPDATE,
        PERM_COMMANDS_DELETE, PERM_COMMANDS_RUN, PERM_COMMANDS_RUN_BULK,
        PERM_COMMANDS_EXPORT, PERM_COMMANDS_SCHEDULE, PERM_INTERFACES_ADMIN,
    }),
    "operator": frozenset({
        PERM_COMMANDS_READ, PERM_COMMANDS_CREATE, PERM_COMMANDS_UPDATE,
        PERM_COMMANDS_RUN, PERM_COMMANDS_RUN_BULK, PERM_COMMANDS_EXPORT,
        PERM_COMMANDS_SCHEDULE,
    }),
    "ai-ops": frozenset({
        PERM_COMMANDS_READ, PERM_COMMANDS_RUN, PERM_COMMANDS_RUN_BULK,
        PERM_COMMANDS_EXPORT,
    }),
    "viewer": frozenset({PERM_COMMANDS_READ}),
}

_ROLE_SETTINGS_PERMS: dict[str, frozenset[str]] = {
    "root": frozenset({"*"}),
    "admin": frozenset({"*"}),
    "operator": frozenset(),
    "ai-ops": frozenset(),
    "viewer": frozenset(),
}


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str = "admin"

    def has_command_perm(self, perm: str) -> bool:
        """Return True if this principal's role grants *perm*."""
        role_perms = _ROLE_COMMAND_PERMS.get(self.role.lower(), frozenset())
        return perm in role_perms

    def has_setting_perm(self, perm: str) -> bool:
        """Return True if this principal's role grants a settings/admin permission."""
        role_perms = _ROLE_SETTINGS_PERMS.get(self.role.lower(), frozenset())
        return "*" in role_perms or perm in role_perms


# ---------------------------------------------------------------------------
# Constant-time API key verification (stdlib only — no bcrypt/argon2 needed
# for env-var/config-driven keys because we never store plaintext in a DB;
# using hmac.compare_digest prevents timing oracles on the comparison itself).
# ---------------------------------------------------------------------------

_SHA256_PREFIX = "sha256$"


def _sha256_digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def _sha256_hexdigest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _key_matches(presented: str, configured_key: str) -> bool:
    """Constant-time match against plaintext or ``sha256$<hex>`` keys."""
    configured_key = configured_key.strip()
    if configured_key.lower().startswith(_SHA256_PREFIX):
        expected_hex = configured_key[len(_SHA256_PREFIX):].strip().lower()
        actual_hex = _sha256_hexdigest(presented)
        if len(expected_hex) != len(actual_hex):
            # Keep compare_digest length-stable for the common SHA-256 path.
            return False
        return hmac.compare_digest(actual_hex, expected_hex)
    return hmac.compare_digest(_sha256_digest(presented), _sha256_digest(configured_key))


def verify_api_key(presented: str, allowed_keys: Iterable[str]) -> bool:
    """Constant-time check: does *presented* match any key in *allowed_keys*.

    Uses hmac.compare_digest over SHA-256 digests to prevent timing oracles.
    Returns True on first match; always runs through all keys to avoid
    short-circuit leakage.
    """
    matched = False
    for key in allowed_keys:
        if _key_matches(presented, key):
            matched = True
        # Do NOT break early — keep iterating to prevent timing leakage.
    return matched


def _configured_keys() -> list[str]:
    raw = settings.api_keys
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [str(item).strip() for item in raw if str(item).strip()]


def configured_api_keys() -> list[str]:
    """Public accessor for callers outside this module (e.g. rate-limit).

    Returns the configured API keys as a list of stripped, non-empty strings.
    Mirrors the internal ``_configured_keys`` helper.
    """
    return _configured_keys()


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
    """FastAPI dependency factory: require the principal to hold any of *roles*.

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


def require_command_permission(perm: str):
    """FastAPI dependency factory: require a specific command permission.

    Uses the role->permission table so a user with only ``commands:read``
    cannot reach run/create/delete endpoints.
    """
    async def _checker(conn: HTTPConnection) -> Principal:
        principal = await require_api_auth(conn)
        if not settings.api_auth_enabled:
            return principal
        if not principal.has_command_perm(perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"permission '{perm}' required; role '{principal.role}' is not sufficient",
            )
        return principal

    return _checker


def require_settings_permission(*perms: str):
    """FastAPI dependency factory: require any settings/admin permission.

    The checks are enforced only when API auth is enabled, matching the command
    authorization behavior and keeping local lab mode frictionless.
    """
    required = tuple(perm for perm in perms if perm)

    async def _checker(conn: HTTPConnection) -> Principal:
        principal = await require_api_auth(conn)
        if not settings.api_auth_enabled:
            return principal
        if not required or any(principal.has_setting_perm(perm) for perm in required):
            return principal
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"one of permissions {required!r} required; role '{principal.role}' is not sufficient",
        )

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

    if not presented or not verify_api_key(presented, allowed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return principal_from_presented_key(presented)


def principal_from_presented_key(presented: str | None) -> Principal:
    """Resolve the principal identity from an already-presented API key.

    This is used by request auditing after authentication has run. It never
    grants access by itself; callers that enforce auth must still use
    ``require_api_auth`` or one of the permission dependencies.
    """
    if not settings.api_auth_enabled:
        return Principal(subject="local-dev")
    if not presented:
        return Principal(subject="anonymous", role="unauthenticated")

    # Resolve role. Role-map keys may be plaintext or sha256$ digests; lookup
    # happens only after authentication succeeds.
    role = next(
        (r for k, r in _role_map().items() if _key_matches(presented, k)),
        "admin",
    )
    return Principal(subject="api-key", role=role)
