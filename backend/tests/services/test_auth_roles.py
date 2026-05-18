"""Tests for role-based gating on API key principals."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import HTTPConnection

from app.config import settings
from app.security.auth import (
    Principal,
    _role_map,
    require_api_auth,
    require_roles,
    roles_from_setting,
)


def _conn(headers: dict[str, str]) -> HTTPConnection:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return HTTPConnection(scope)


def test_roles_from_setting_parses_csv():
    assert roles_from_setting("admin, AI-Ops , viewer") == ("admin", "ai-ops", "viewer")


def test_roles_from_setting_handles_list():
    assert roles_from_setting(["Admin", "Viewer "]) == ("admin", "viewer")


def test_role_map_parses_key_role_pairs(monkeypatch):
    monkeypatch.setattr(settings, "api_key_roles", " k1:admin , k2:ai-ops , junk , :viewer ")
    assert _role_map() == {"k1": "admin", "k2": "ai-ops"}


def test_require_api_auth_returns_local_dev_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    p = asyncio.run(require_api_auth(_conn({})))
    assert isinstance(p, Principal)
    assert p.role == "admin"


def test_require_api_auth_resolves_role_from_map(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "secret-key")
    monkeypatch.setattr(settings, "api_key_roles", "secret-key:ai-ops")
    p = asyncio.run(require_api_auth(_conn({"x-api-key": "secret-key"})))
    assert p.role == "ai-ops"


def test_require_api_auth_defaults_to_admin_when_key_unmapped(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "k")
    monkeypatch.setattr(settings, "api_key_roles", "")
    p = asyncio.run(require_api_auth(_conn({"x-api-key": "k"})))
    assert p.role == "admin"


def test_require_roles_allows_matching_role(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "k")
    monkeypatch.setattr(settings, "api_key_roles", "k:ai-ops")
    dep = require_roles("admin", "ai-ops")
    p = asyncio.run(dep(_conn({"x-api-key": "k"})))
    assert p.role == "ai-ops"


def test_require_roles_rejects_mismatched_role(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "k")
    monkeypatch.setattr(settings, "api_key_roles", "k:viewer")
    dep = require_roles("admin", "ai-ops")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(dep(_conn({"x-api-key": "k"})))
    assert exc.value.status_code == 403


def test_require_roles_passthrough_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    dep = require_roles("admin")
    p = asyncio.run(dep(_conn({})))
    assert p.role == "admin"
