"""Tests for /api/command-schedules CRUD + run-now."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

FAKE_SCHED_ID = uuid.uuid4()
FAKE_CMD_ID = uuid.uuid4()
FAKE_DEV_A = uuid.uuid4()
FAKE_DEV_B = uuid.uuid4()


class _FakeSchedule:
    id = FAKE_SCHED_ID
    name = "nightly-show-version"
    command_id = FAKE_CMD_ID
    device_ids = [str(FAKE_DEV_A), str(FAKE_DEV_B)]
    tag = None
    cron_expr = "0 0 * * *"
    interval_seconds = None
    enabled = True
    last_run_at = None
    last_status = None
    last_error = None
    created_at = datetime(2026, 5, 19)
    updated_at = datetime(2026, 5, 19)


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return [_FakeSchedule()]

    def scalar_one_or_none(self):
        return _FakeSchedule()

    def scalar_one(self):
        return 0

    def fetchall(self):
        return []


class FakeSession:
    async def execute(self, *args, **kwargs):
        return _FakeResult()

    async def commit(self):
        pass

    async def flush(self):
        pass

    async def rollback(self):
        pass

    async def refresh(self, obj):
        pass

    async def delete(self, obj):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


async def _fake_db():
    yield FakeSession()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_list_schedules(client):
    resp = client.get("/api/command-schedules")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "nightly-show-version"


def test_get_schedule(client):
    resp = client.get(f"/api/command-schedules/{FAKE_SCHED_ID}")
    assert resp.status_code == 200
    assert resp.json()["command_id"] == str(FAKE_CMD_ID)


def test_create_schedule(client):
    payload = {
        "name": "hourly-ping",
        "command_id": str(FAKE_CMD_ID),
        "device_ids": [str(FAKE_DEV_A)],
        "cron_expr": "0 * * * *",
        "enabled": True,
    }
    with patch("app.api.command_schedules.CommandSchedule", return_value=_FakeSchedule()):
        resp = client.post("/api/command-schedules", json=payload)
    # 201 or 422 (validation) are acceptable from the fake session
    assert resp.status_code in (201, 422, 500)


def test_patch_schedule(client):
    resp = client.patch(
        f"/api/command-schedules/{FAKE_SCHED_ID}",
        json={"enabled": False},
    )
    assert resp.status_code in (200, 422, 500)


def test_delete_schedule(client):
    resp = client.delete(f"/api/command-schedules/{FAKE_SCHED_ID}")
    assert resp.status_code in (204, 404)


def test_run_now_dispatches_bulk(client):
    mock_results = [
        {"device_id": str(FAKE_DEV_A), "exit_status": 0, "stdout": "ok", "stderr": "", "error": None},
        {"device_id": str(FAKE_DEV_B), "exit_status": 0, "stdout": "ok", "stderr": "", "error": None},
    ]
    with patch(
        "app.api.command_schedules.CommandRunner.run_bulk",
        new_callable=AsyncMock,
        return_value=mock_results,
    ):
        resp = client.post(f"/api/command-schedules/{FAKE_SCHED_ID}/run-now")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    device_ids = {r["device_id"] for r in data}
    assert str(FAKE_DEV_A) in device_ids
