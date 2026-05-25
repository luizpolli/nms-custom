"""Tests for alarm CSV export."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.alarm import Alarm


ALARM_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")


def _alarm() -> Alarm:
    return Alarm(
        id=ALARM_ID,
        source_host="core-1",
        severity="critical",
        category="link",
        event_type="linkDown",
        message="Interface GigabitEthernet0/0 is down",
        trap_oid="1.3.6.1.6.3.1.1.5.3",
        correlation_key="core-1:linkDown:Gi0/0",
        state="active",
        first_seen=datetime(2026, 5, 24, 12, 0, tzinfo=timezone.utc),
        last_seen=datetime(2026, 5, 24, 12, 5, tzinfo=timezone.utc),
        occurrence_count=3,
    )


class _FakeResult:
    def scalars(self):
        return self

    def all(self):
        return [_alarm()]


class _FakeSession:
    async def execute(self, *args, **kwargs):
        return _FakeResult()

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


def test_alarm_csv_export_all_matching_filters(client: TestClient):
    response = client.get("/api/alarms/export?format=csv&severity=critical&state=active")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    rows = _csv_rows(response)
    assert rows[0]["Alarm ID"] == str(ALARM_ID)
    assert rows[0]["Severity"] == "critical"
    assert rows[0]["State"] == "active"
    assert rows[0]["Source Host"] == "core-1"
    assert rows[0]["Occurrences"] == "3"


def test_alarm_csv_export_selected_filename(client: TestClient):
    response = client.get(f"/api/alarms/export?format=csv&alarm_ids={ALARM_ID}")

    assert response.status_code == 200
    assert 'filename="alarms_selected_export.csv"' in response.headers["content-disposition"]
    rows = _csv_rows(response)
    assert rows[0]["Event Type"] == "linkDown"
