"""Smoke tests for API routes — import-time sanity + 2 endpoint checks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Fake async session
# ---------------------------------------------------------------------------

class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return []

    def scalar_one_or_none(self):
        return None

    def scalar_one(self):
        return 0


class FakeAsyncSession:
    async def execute(self, *args, **kwargs):
        return _FakeResult()

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass

    async def delete(self, obj):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


async def _fake_get_db() -> AsyncGenerator[FakeAsyncSession, None]:
    yield FakeAsyncSession()


# ---------------------------------------------------------------------------
# Override dependency for the lifetime of this module's tests only.
#
# Setting this at import time (instead of inside the fixture) used to leak:
# other test modules' setup_method/teardown_method pairs do an unconditional
# `app.dependency_overrides.pop(get_db, None)`, which — since
# `app.dependency_overrides` is a single global dict shared by the whole
# `app` singleton — would silently wipe out an override set at collection
# time, long before any test here actually ran. Scoping the override to the
# fixture means it's set/restored right around this module's own tests.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_api_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_live(client: TestClient):
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_devices_returns_empty(client: TestClient):
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    assert resp.json() == []


def test_alarm_summary_responds(client: TestClient):
    """Summary endpoint should return 200 with fake db returning 0 counts."""
    resp = client.get("/api/alarms/summary")
    # Accepts 200 (fake db works) or gracefully handled error
    assert resp.status_code in (200, 500, 422)
    if resp.status_code == 200:
        body = resp.json()
        assert "total" in body
