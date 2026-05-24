"""Tests for EPNM-style device CSV export."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.credential import Credential
from app.models.device import Device
from app.models.inventory import Inventory


def _device() -> Device:
    cred_id = uuid.uuid4()
    device_id = uuid.uuid4()
    credential = Credential(
        id=cred_id,
        name="core-profile",
        hostname="10.0.0.1",
        username="snmp-user",
        auth_key="encrypted-auth",
        enc_key="encrypted-priv",
        protocol="snmp",
        snmp_version="v3",
        port=161,
        created_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device_id,
        firmware_version="IOS XR 7.10.2",
        additional_info={"collection_status": "Success"},
        created_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
    )
    device = Device(
        id=device_id,
        name="core-1",
        ip_address="10.0.0.1",
        device_type="router",
        vendor="Cisco",
        os_type="ios-xr",
        status="reachable",
        lifecycle_state="active",
        credential_id=cred_id,
        created_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, tzinfo=timezone.utc),
    )
    device.credential = credential
    device.inventory = inventory
    return device


class _FakeResult:
    def __init__(self, rows: list[Device]):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    async def execute(self, *args, **kwargs):
        return _FakeResult([_device()])

    async def commit(self):
        pass

    async def rollback(self):
        pass


async def _fake_db() -> AsyncGenerator[_FakeSession, None]:
    yield _FakeSession()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "api_auth_enabled", False)
    prev = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    if prev is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = prev


def _csv_rows(response) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(response.text)))


def test_csv_export_without_credentials(client: TestClient):
    response = client.get("/api/devices/export?format=csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    rows = _csv_rows(response)
    assert rows[0]["Reachability"] == "reachable"
    assert rows[0]["Device Name"] == "core-1"
    assert rows[0]["Software Version"] == "IOS XR 7.10.2"
    assert "SNMPv3 Auth Password" not in rows[0]


def test_csv_export_with_credentials_uses_vault(client: TestClient):
    vault = MagicMock()
    vault.decrypt.side_effect = ["auth-secret", "priv-secret"]

    with patch("app.api.devices.CredentialVault.from_settings", return_value=vault):
        response = client.get("/api/devices/export?format=csv&include_credentials=true")

    assert response.status_code == 200
    rows = _csv_rows(response)
    assert rows[0]["SNMP Version"] == "v3"
    assert rows[0]["SNMPv3 Username"] == "snmp-user"
    assert rows[0]["SNMPv3 Auth Password"] == "auth-secret"
    assert rows[0]["SNMPv3 Privacy Password"] == "priv-secret"
    assert rows[0]["Credential Profile"] == "core-profile"


def test_non_root_user_cannot_export_credentials(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "api_auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", "operator-key")
    monkeypatch.setattr(settings, "api_key_roles", "operator-key:operator")

    response = client.get(
        "/api/devices/export?format=csv&include_credentials=true",
        headers={"X-API-Key": "operator-key"},
    )

    assert response.status_code == 403
