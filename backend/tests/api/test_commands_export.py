"""Tests for command run export — download, email no-op, file write + traversal guard."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

FAKE_CMD_ID = uuid.uuid4()
FAKE_DEV_ID = uuid.uuid4()
_NOW = datetime(2026, 5, 19, 12, 0, 0)


class _FakeRun:
    id = uuid.uuid4()
    command_id = FAKE_CMD_ID
    device_id = FAKE_DEV_ID
    started_at = _NOW
    finished_at = _NOW
    exit_status = 0
    stdout = "IOS XR 7.8.1"
    stderr = ""
    triggered_by = "manual"


class _FakeCommand:
    id = FAKE_CMD_ID
    device_id = FAKE_DEV_ID
    name = "show-ver"
    cli_command = "show version"
    output_path = None
    last_output = None


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return [_FakeRun()]

    def scalar_one_or_none(self):
        return _FakeCommand()

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


def test_export_download_txt(client):
    resp = client.post(
        f"/api/commands/{FAKE_CMD_ID}/runs/export",
        json={"format": "txt", "delivery": "download"},
    )
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert b"IOS XR 7.8.1" in resp.content


def test_export_download_json(client):
    resp = client.post(
        f"/api/commands/{FAKE_CMD_ID}/runs/export",
        json={"format": "json", "delivery": "download"},
    )
    assert resp.status_code == 200
    assert "application/json" in resp.headers["content-type"]
    import json
    data = json.loads(resp.content)
    assert isinstance(data, list)
    assert data[0]["stdout"] == "IOS XR 7.8.1"


def test_export_download_csv(client):
    resp = client.post(
        f"/api/commands/{FAKE_CMD_ID}/runs/export",
        json={"format": "csv", "delivery": "download"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert b"exit_status" in resp.content  # header row


def test_export_email_noop_when_smtp_unset(client):
    """When SMTP_HOST is not set, send_email returns False — endpoint returns sent=false."""
    env = {k: v for k, v in os.environ.items() if k != "SMTP_HOST"}
    with patch.dict(os.environ, env, clear=True):
        resp = client.post(
            f"/api/commands/{FAKE_CMD_ID}/runs/export",
            json={"format": "json", "delivery": "email", "recipients": ["ops@example.com"]},
        )
    assert resp.status_code == 200
    import json
    body = json.loads(resp.content)
    assert body["sent"] is False


def test_export_email_requires_recipients(client):
    resp = client.post(
        f"/api/commands/{FAKE_CMD_ID}/runs/export",
        json={"format": "json", "delivery": "email", "recipients": []},
    )
    assert resp.status_code == 422


def test_export_file_write(client, tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with patch.dict(os.environ, {"COMMAND_ARTIFACTS_DIR": str(artifacts_dir)}):
        # Reimport module so env var is picked up
        import importlib
        import app.services.command_export as ce
        importlib.reload(ce)
        # Patch export_to_file in the commands api to use our reloaded version
        with patch("app.api.commands.export_to_file", wraps=ce.export_to_file):
            resp = client.post(
                f"/api/commands/{FAKE_CMD_ID}/runs/export",
                json={"format": "txt", "delivery": "file", "target_path": "myexport.txt"},
            )
    assert resp.status_code == 200
    import json
    body = json.loads(resp.content)
    assert "path" in body


def test_export_file_traversal_rejected(client, tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    with patch.dict(os.environ, {"COMMAND_ARTIFACTS_DIR": str(artifacts_dir)}):
        import importlib
        import app.services.command_export as ce
        importlib.reload(ce)
        with patch("app.api.commands.export_to_file", wraps=ce.export_to_file):
            resp = client.post(
                f"/api/commands/{FAKE_CMD_ID}/runs/export",
                json={"format": "txt", "delivery": "file", "target_path": "../../etc/passwd"},
            )
    assert resp.status_code == 422
