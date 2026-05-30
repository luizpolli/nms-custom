"""Security regression tests: Host header allow-list enforcement.

TrustedHostMiddleware is the outermost layer in the ASGI stack.  Every
request whose Host header is not in ALLOWED_HOSTS must be rejected with 400
*before* any route handler or authentication logic runs.

These tests cover both the middleware in isolation (fast, hermetic) and its
integration with the real ``app.main`` application object to guard against
accidental misconfiguration during startup.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import DEFAULT_ALLOWED_HOSTS, Settings
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(allowed_hosts: list[str]) -> TestClient:
    """Return a TestClient backed by a minimal app with TrustedHostMiddleware."""
    mini = FastAPI()
    mini.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @mini.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    return TestClient(mini, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Middleware isolation tests
# ---------------------------------------------------------------------------


def test_trusted_host_rejects_arbitrary_external_host() -> None:
    """An arbitrary external host must be rejected with HTTP 400."""
    client = _make_client(DEFAULT_ALLOWED_HOSTS)
    resp = client.get("/ping", headers={"host": "attacker.example.com"})
    assert resp.status_code == 400


def test_trusted_host_rejects_subdomain_of_allowed_host() -> None:
    """Subdomains of an allowed host must not be accepted (no implicit wildcard)."""
    client = _make_client(["example.com"])
    resp = client.get("/ping", headers={"host": "evil.example.com"})
    assert resp.status_code == 400


def test_trusted_host_rejects_numeric_ip_not_in_allowlist() -> None:
    """An IP address that isn't in the allowlist must be rejected."""
    client = _make_client(["localhost"])
    resp = client.get("/ping", headers={"host": "10.0.0.1"})
    assert resp.status_code == 400


def test_trusted_host_accepts_listed_host() -> None:
    """A host explicitly listed must be accepted."""
    client = _make_client(["myhost.internal"])
    resp = client.get("/ping", headers={"host": "myhost.internal"})
    assert resp.status_code == 200


def test_trusted_host_accepts_localhost() -> None:
    """localhost is always in the default allow-list."""
    client = _make_client(DEFAULT_ALLOWED_HOSTS)
    resp = client.get("/ping", headers={"host": "localhost"})
    assert resp.status_code == 200


def test_trusted_host_accepts_localhost_with_port() -> None:
    """Host with port suffix must still match the base hostname."""
    client = _make_client(DEFAULT_ALLOWED_HOSTS)
    resp = client.get("/ping", headers={"host": "localhost:8080"})
    assert resp.status_code == 200


def test_trusted_host_wildcard_accepts_any_host() -> None:
    """Wildcard (*) must allow any Host value."""
    client = _make_client(["*"])
    resp = client.get("/ping", headers={"host": "literally-anything.io"})
    assert resp.status_code == 200


def test_trusted_host_rejects_path_traversal_in_host() -> None:
    """Host values containing path separators are not legitimate hostnames."""
    client = _make_client(DEFAULT_ALLOWED_HOSTS)
    resp = client.get("/ping", headers={"host": "localhost/../admin"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Settings parsing tests
# ---------------------------------------------------------------------------


def test_settings_allowed_hosts_parses_csv() -> None:
    """allowed_hosts given as a CSV string must be split into a list."""
    s = Settings(allowed_hosts="nms.corp.com,nms2.corp.com")
    assert s.allowed_hosts == ["nms.corp.com", "nms2.corp.com"]


def test_settings_allowed_hosts_accepts_wildcard_string() -> None:
    s = Settings(allowed_hosts="*")
    assert s.allowed_hosts == ["*"]


def test_settings_allowed_hosts_falls_back_to_defaults_when_empty() -> None:
    """An empty ALLOWED_HOSTS must not produce an empty list (that blocks every request)."""
    s = Settings(allowed_hosts="")
    assert s.allowed_hosts  # non-empty
    assert "localhost" in s.allowed_hosts


# ---------------------------------------------------------------------------
# Full-app integration: Host allow-listing fires on the real app
# ---------------------------------------------------------------------------


def test_app_rejects_disallowed_host() -> None:
    """The real app must reject an untrusted Host header."""
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/health", headers={"host": "not-in-allowlist.example"})
    assert resp.status_code == 400


def test_app_accepts_testserver_host() -> None:
    """TestClient uses ``testserver`` by default, which is in DEFAULT_ALLOWED_HOSTS."""
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/health")
    assert resp.status_code == 200


def test_app_health_returns_ok_for_trusted_host() -> None:
    """Health endpoint must return 200 for requests with a trusted Host."""
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/health", headers={"host": "localhost"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
