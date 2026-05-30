"""Tests for the request rate-limit middleware (P0.4).

The middleware is wired up in ``app.main`` but skipped when ``APP_ENV=test``,
so these tests build a tiny FastAPI app and attach the middleware directly
with low limits to keep the suite fast and hermetic. The in-memory backend
is used throughout — no Redis is needed.
"""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.rate_limit import (
    RateLimitMiddleware,
    RateLimitRule,
    _MemoryStore,
)


# Each test gets its own app + store so counters never leak between cases.
def _make_app(
    *,
    default: str = "5/60",
    sensitive: str = "2/60",
    anonymous: str = "3/60",
    exempt: str = "/api/health,/health,/metrics",
    enabled: bool = True,
    app_env: str = "production",
    api_keys: str = "",
) -> FastAPI:
    # Patch settings in-place before the middleware reads them. We restore
    # at the end of each test via monkeypatch in the test functions.
    from app.config import settings as s

    s.rate_limit_enabled = enabled
    s.rate_limit_default = default
    s.rate_limit_sensitive = sensitive
    s.rate_limit_anonymous = anonymous
    s.rate_limit_exempt_paths = exempt
    s.app_env = app_env
    s.api_keys = api_keys

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, store=_MemoryStore())

    @app.get("/api/devices")
    async def list_devices() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/api/devices")
    async def create_device() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/api/credentials")
    async def create_credential() -> dict[str, str]:
        return {"ok": "true"}

    @app.post("/api/commands/run")
    async def run_command() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/api/health")
    async def api_health() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/metrics")
    async def metrics() -> dict[str, str]:
        return {"ok": "true"}

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"ok": "true"}

    return app


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch):
    """Snapshot rate-limit-relevant settings so tests stay isolated."""
    from app.config import settings as s

    snapshot = {
        "rate_limit_enabled": s.rate_limit_enabled,
        "rate_limit_default": s.rate_limit_default,
        "rate_limit_sensitive": s.rate_limit_sensitive,
        "rate_limit_anonymous": s.rate_limit_anonymous,
        "rate_limit_exempt_paths": s.rate_limit_exempt_paths,
        "app_env": s.app_env,
        "api_keys": s.api_keys,
    }
    yield
    for k, v in snapshot.items():
        setattr(s, k, v)


# ----- rule parsing ----------------------------------------------------------


def test_rule_parse_valid() -> None:
    rule = RateLimitRule.parse("default", "120/60")
    assert rule.limit == 120
    assert rule.window_seconds == 60
    assert rule.name == "default"


@pytest.mark.parametrize("raw", ["120", "abc/60", "0/60", "10/0", "10/-5"])
def test_rule_parse_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError):
        RateLimitRule.parse("default", raw)


# ----- happy path & 429 ------------------------------------------------------


def test_anonymous_get_blocked_after_burst() -> None:
    app = _make_app(anonymous="3/60")
    client = TestClient(app)
    for i in range(3):
        r = client.get("/api/devices")
        assert r.status_code == 200, f"req {i} unexpectedly blocked"
        assert r.headers["X-RateLimit-Rule"] == "anonymous"
    blocked = client.get("/api/devices")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["X-RateLimit-Limit"] == "3"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_authenticated_uses_default_bucket() -> None:
    app = _make_app(default="5/60", anonymous="2/60", api_keys="mykey-1234567890abcd")
    client = TestClient(app)
    headers = {"X-API-Key": "mykey-1234567890abcd"}
    # The anonymous bucket is tighter (2) — if auth were ignored, we'd 429 at request 3.
    for i in range(5):
        r = client.get("/api/devices", headers=headers)
        assert r.status_code == 200, f"req {i} blocked despite valid key"
        assert r.headers["X-RateLimit-Rule"] == "default"
    assert client.get("/api/devices", headers=headers).status_code == 429


def test_unknown_api_key_does_not_promote_to_auth_bucket() -> None:
    """Garbage keys must NOT widen the limit; counted under the IP bucket."""
    app = _make_app(default="100/60", anonymous="2/60", api_keys="real-key-1234567890ab")
    client = TestClient(app)
    bad = {"X-API-Key": "totally-not-real"}
    assert client.get("/api/devices", headers=bad).status_code == 200
    assert client.get("/api/devices", headers=bad).status_code == 200
    # Anonymous bucket exhausted under the IP key; next call must 429
    # even though the request "looks" authenticated.
    r3 = client.get("/api/devices", headers=bad)
    assert r3.status_code == 429
    assert r3.headers["X-RateLimit-Rule"] == "anonymous"


def test_garbage_key_rotation_does_not_bypass_limit() -> None:
    """Spraying different garbage keys still hits the same IP bucket."""
    app = _make_app(anonymous="2/60")
    client = TestClient(app)
    assert client.get("/api/devices", headers={"X-API-Key": "garbage-A"}).status_code == 200
    assert client.get("/api/devices", headers={"X-API-Key": "garbage-B"}).status_code == 200
    r = client.get("/api/devices", headers={"X-API-Key": "garbage-C"}).status_code
    assert r == 429


def test_sensitive_prefix_uses_tighter_bucket() -> None:
    app = _make_app(
        default="100/60",
        sensitive="2/60",
        api_keys="key1-1234567890abcdef",
    )
    client = TestClient(app)
    h = {"X-API-Key": "key1-1234567890abcdef"}
    assert client.post("/api/credentials", headers=h).status_code == 200
    assert client.post("/api/credentials", headers=h).status_code == 200
    r = client.post("/api/credentials", headers=h)
    assert r.status_code == 429
    assert r.headers["X-RateLimit-Rule"] == "sensitive"


def test_command_run_uses_sensitive_bucket() -> None:
    app = _make_app(default="100/60", sensitive="1/60", api_keys="key1-1234567890abcdef")
    client = TestClient(app)
    h = {"X-API-Key": "key1-1234567890abcdef"}
    assert client.post("/api/commands/run", headers=h).status_code == 200
    assert client.post("/api/commands/run", headers=h).status_code == 429


def test_unauth_write_uses_sensitive_bucket() -> None:
    """An anonymous POST is a cheap abuse vector; must use the tight bucket."""
    app = _make_app(anonymous="100/60", sensitive="1/60")
    client = TestClient(app)
    assert client.post("/api/devices").status_code == 200
    r = client.post("/api/devices")
    assert r.status_code == 429
    assert r.headers["X-RateLimit-Rule"] == "sensitive"


# ----- exemptions & toggles --------------------------------------------------


def test_health_path_is_exempt() -> None:
    app = _make_app(anonymous="1/60")
    client = TestClient(app)
    for _ in range(20):
        assert client.get("/api/health").status_code == 200


def test_metrics_path_is_exempt() -> None:
    app = _make_app(anonymous="1/60")
    client = TestClient(app)
    for _ in range(20):
        assert client.get("/metrics").status_code == 200


def test_non_api_path_is_exempt() -> None:
    """Root and any non-/api path is out of scope for this middleware."""
    app = _make_app(anonymous="1/60")
    client = TestClient(app)
    for _ in range(10):
        assert client.get("/").status_code == 200


def test_test_env_disables_middleware() -> None:
    app = _make_app(anonymous="1/60", app_env="test")
    client = TestClient(app)
    for _ in range(50):
        assert client.get("/api/devices").status_code == 200


def test_disabled_flag_disables_middleware() -> None:
    app = _make_app(anonymous="1/60", enabled=False)
    client = TestClient(app)
    for _ in range(50):
        assert client.get("/api/devices").status_code == 200


# ----- response headers on the success path ---------------------------------


def test_success_headers_include_remaining_and_rule() -> None:
    app = _make_app(anonymous="3/60")
    client = TestClient(app)
    r1 = client.get("/api/devices")
    assert r1.headers["X-RateLimit-Limit"] == "3"
    assert r1.headers["X-RateLimit-Remaining"] == "2"
    assert r1.headers["X-RateLimit-Rule"] == "anonymous"
    r2 = client.get("/api/devices")
    assert r2.headers["X-RateLimit-Remaining"] == "1"
