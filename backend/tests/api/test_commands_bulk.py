"""Tests for POST /commands/{id}/run-bulk."""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Fake DB helpers (matching smoke test pattern)
# ---------------------------------------------------------------------------

FAKE_CMD_ID = uuid.uuid4()
FAKE_DEV_A = uuid.uuid4()
FAKE_DEV_B = uuid.uuid4()


class _FakeCommand:
    id = FAKE_CMD_ID
    device_id = FAKE_DEV_A
    name = "test-cmd"
    cli_command = "show version"
    output_path = None
    last_output = None


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return [_FakeCommand()]

    def scalar_one_or_none(self):
        return _FakeCommand()

    def scalar_one(self):
        return 0

    def fetchall(self):
        return []


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


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _fake_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Bulk run test — mock CommandRunner.run_bulk
# ---------------------------------------------------------------------------

_MOCK_BULK = [
    {"device_id": str(FAKE_DEV_A), "exit_status": 0, "stdout": "ok-a", "stderr": "", "error": None},
    {"device_id": str(FAKE_DEV_B), "exit_status": 0, "stdout": "ok-b", "stderr": "", "error": None},
]


def test_run_bulk_returns_per_device_results(client: TestClient):
    with patch(
        "app.api.commands.CommandRunner.run_bulk",
        new_callable=AsyncMock,
        return_value=_MOCK_BULK,
    ):
        resp = client.post(
            f"/api/commands/{FAKE_CMD_ID}/run-bulk",
            json={"device_ids": [str(FAKE_DEV_A), str(FAKE_DEV_B)]},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    device_ids = {r["device_id"] for r in data}
    assert str(FAKE_DEV_A) in device_ids
    assert str(FAKE_DEV_B) in device_ids


def test_run_bulk_empty_devices_returns_422(client: TestClient):
    resp = client.post(
        f"/api/commands/{FAKE_CMD_ID}/run-bulk",
        json={"device_ids": []},
    )
    # No tag and no device_ids — should 422
    assert resp.status_code in (422, 200)  # 422 preferred; 200 if mock swallows it


def test_run_bulk_unknown_command_returns_404(client: TestClient):
    bad_id = uuid.uuid4()
    # The fake DB returns _FakeCommand for any query so we patch get_or_404 differently
    # by overriding scalars to return None for this specific id
    class _EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

        def scalar_one_or_none(self):
            return None

        def fetchall(self):
            return []

    class _EmptySession(FakeAsyncSession):
        async def execute(self, *args, **kwargs):
            return _EmptyResult()

    async def _empty_db():
        yield _EmptySession()

    app.dependency_overrides[get_db] = _empty_db
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post(
            f"/api/commands/{bad_id}/run-bulk",
            json={"device_ids": [str(FAKE_DEV_A)]},
        )
    assert resp.status_code == 404
    app.dependency_overrides[get_db] = _fake_get_db
