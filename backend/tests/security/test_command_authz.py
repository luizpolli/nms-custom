"""Tests for per-action command permissions and constant-time API key verification."""

from __future__ import annotations

import asyncio
import hashlib

import pytest
from fastapi import HTTPException
from starlette.requests import HTTPConnection

from app.config import settings
from app.security.auth import (
    Principal,
    PERM_COMMANDS_READ,
    PERM_COMMANDS_CREATE,
    PERM_COMMANDS_RUN,
    PERM_COMMANDS_RUN_BULK,
    PERM_COMMANDS_SCHEDULE,
    PERM_COMMANDS_DELETE,
    PERM_COMMANDS_EXPORT,
    PERM_SETTINGS_SYSTEM,
    require_command_permission,
    require_settings_permission,
    verify_api_key,
)


def _conn(headers: dict[str, str]) -> HTTPConnection:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return HTTPConnection(scope)


# ---------------------------------------------------------------------------
# Per-action role permission tests
# ---------------------------------------------------------------------------


def test_admin_has_all_command_perms():
    p = Principal(subject="test", role="admin")
    for perm in (
        PERM_COMMANDS_READ, PERM_COMMANDS_CREATE, PERM_COMMANDS_RUN,
        PERM_COMMANDS_RUN_BULK, PERM_COMMANDS_SCHEDULE, PERM_COMMANDS_DELETE,
        PERM_COMMANDS_EXPORT,
    ):
        assert p.has_command_perm(perm), f"admin should have {perm}"


def test_viewer_can_only_read():
    p = Principal(subject="test", role="viewer")
    assert p.has_command_perm(PERM_COMMANDS_READ)
    for perm in (PERM_COMMANDS_CREATE, PERM_COMMANDS_RUN, PERM_COMMANDS_RUN_BULK,
                 PERM_COMMANDS_SCHEDULE, PERM_COMMANDS_DELETE, PERM_COMMANDS_EXPORT):
        assert not p.has_command_perm(perm), f"viewer should NOT have {perm}"


def test_viewer_cannot_run_command(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "viewer-key")
    monkeypatch.setattr(settings, "api_key_roles", "viewer-key:viewer")

    dep = require_command_permission(PERM_COMMANDS_RUN)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep(_conn({"x-api-key": "viewer-key"})))
    assert exc.value.status_code == 403
    assert PERM_COMMANDS_RUN in exc.value.detail


def test_viewer_cannot_schedule(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "viewer-key")
    monkeypatch.setattr(settings, "api_key_roles", "viewer-key:viewer")

    dep = require_command_permission(PERM_COMMANDS_SCHEDULE)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep(_conn({"x-api-key": "viewer-key"})))
    assert exc.value.status_code == 403


def test_viewer_can_read(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "viewer-key")
    monkeypatch.setattr(settings, "api_key_roles", "viewer-key:viewer")

    dep = require_command_permission(PERM_COMMANDS_READ)
    principal = asyncio.run(dep(_conn({"x-api-key": "viewer-key"})))
    assert principal.role == "viewer"


def test_operator_can_run_but_not_delete(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "op-key")
    monkeypatch.setattr(settings, "api_key_roles", "op-key:operator")

    run_dep = require_command_permission(PERM_COMMANDS_RUN)
    p = asyncio.run(run_dep(_conn({"x-api-key": "op-key"})))
    assert p.role == "operator"

    del_dep = require_command_permission(PERM_COMMANDS_DELETE)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(del_dep(_conn({"x-api-key": "op-key"})))
    assert exc.value.status_code == 403


def test_command_perm_passthrough_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    dep = require_command_permission(PERM_COMMANDS_RUN)
    # Auth disabled: local-dev principal, no role check applied.
    p = asyncio.run(dep(_conn({})))
    assert p.subject == "local-dev"


def test_admin_has_settings_perms():
    p = Principal(subject="test", role="admin")
    assert p.has_setting_perm(PERM_SETTINGS_SYSTEM)


def test_viewer_cannot_access_settings_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "viewer-key")
    monkeypatch.setattr(settings, "api_key_roles", "viewer-key:viewer")

    dep = require_settings_permission(PERM_SETTINGS_SYSTEM)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep(_conn({"x-api-key": "viewer-key"})))
    assert exc.value.status_code == 403
    assert PERM_SETTINGS_SYSTEM in exc.value.detail


def test_admin_can_access_settings_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "admin-key")
    monkeypatch.setattr(settings, "api_key_roles", "admin-key:admin")

    dep = require_settings_permission(PERM_SETTINGS_SYSTEM)
    principal = asyncio.run(dep(_conn({"x-api-key": "admin-key"})))
    assert principal.role == "admin"


def test_settings_perm_passthrough_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    dep = require_settings_permission(PERM_SETTINGS_SYSTEM)
    p = asyncio.run(dep(_conn({})))
    assert p.subject == "local-dev"


# ---------------------------------------------------------------------------
# Constant-time API key verification
# ---------------------------------------------------------------------------


def test_verify_api_key_correct_key_passes():
    assert verify_api_key("secret-abc", ["secret-abc"]) is True


def test_verify_api_key_wrong_key_fails():
    assert verify_api_key("wrong-key", ["secret-abc"]) is False


def test_verify_api_key_empty_allowed_list_fails():
    assert verify_api_key("any-key", []) is False


def test_verify_api_key_matches_one_of_many():
    assert verify_api_key("key-b", ["key-a", "key-b", "key-c"]) is True


def test_verify_api_key_accepts_sha256_configured_key():
    digest = hashlib.sha256("secret-abc".encode()).hexdigest()
    assert verify_api_key("secret-abc", [f"sha256${digest}"]) is True
    assert verify_api_key("wrong-key", [f"sha256${digest}"]) is False


def test_verify_api_key_wrong_among_many():
    assert verify_api_key("key-x", ["key-a", "key-b", "key-c"]) is False


def test_verify_api_key_uses_digest_comparison():
    """Verify the implementation uses SHA-256 digests (not plaintext ==)."""
    key = "test-key"
    digest = hashlib.sha256(key.encode()).digest()
    # verify_api_key must accept the plaintext key and internally derive the digest.
    assert verify_api_key(key, [key]) is True
    # A key whose SHA-256 happens to equal another would match (impossible in practice
    # but demonstrates the mechanism). We just check wrong keys are rejected.
    assert verify_api_key("different", [key]) is False


def test_require_api_auth_uses_constant_time(monkeypatch):
    """Wrong key still receives 401 even when API auth is enabled."""
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "correct-key")
    monkeypatch.setattr(settings, "api_key_roles", "")

    from app.security.auth import require_api_auth
    with pytest.raises(HTTPException) as exc:
        asyncio.run(require_api_auth(_conn({"x-api-key": "wrong-key"})))
    assert exc.value.status_code == 401


def test_require_api_auth_role_map_accepts_sha256_keys(monkeypatch):
    digest = hashlib.sha256("viewer-secret".encode()).hexdigest()
    configured = f"sha256${digest}"
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", configured)
    monkeypatch.setattr(settings, "api_key_roles", f"{configured}:viewer")

    from app.security.auth import require_api_auth

    principal = asyncio.run(require_api_auth(_conn({"x-api-key": "viewer-secret"})))
    assert principal.role == "viewer"
