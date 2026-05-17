"""Tests for system self-observability endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.observability.heartbeat import WorkerStatus


def test_system_health_reports_worker_summary(monkeypatch):
    async def fake_get_all_worker_status():
        return [
            WorkerStatus(kind="monitoring-policies", last_status="ok", runs_total=3),
            WorkerStatus(kind="topology", last_status="error", errors_total=1, is_stale=True),
        ]

    monkeypatch.setattr("app.api.system.get_all_worker_status", fake_get_all_worker_status)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/system/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["summary"] == {
        "worker_count": 2,
        "stale_count": 1,
        "stale_workers": ["topology"],
    }
    assert body["workers"][0]["kind"] == "monitoring-policies"
    assert body["workers"][1]["is_stale"] is True


def test_system_health_ok_when_no_stale_workers(monkeypatch):
    async def fake_get_all_worker_status():
        return [WorkerStatus(kind="report-scheduler", last_status="ok", runs_total=1)]

    monkeypatch.setattr("app.api.system.get_all_worker_status", fake_get_all_worker_status)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/system/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["summary"]["stale_count"] == 0
