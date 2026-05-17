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


def test_system_retention_reports_policies(monkeypatch):
    async def fake_ensure_timescale_schema(db):
        return {"extension": "ok", "retention.kpis": "90d"}

    monkeypatch.setattr("app.api.system.ensure_timescale_schema", fake_ensure_timescale_schema)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/system/retention")

    assert resp.status_code == 200
    body = resp.json()
    assert body["timescale"]["extension"] == "ok"
    assert {policy["table"] for policy in body["policies"]} == {"kpis", "telemetry_raw_samples"}


def test_prometheus_metrics_endpoint_exposes_nms_metrics(monkeypatch):
    from app.services.observability.metrics import MetricsSnapshot

    async def fake_snapshot():
        return MetricsSnapshot(kpi_rows=7, raw_telemetry_rows=3, telemetry_samples_total=11, telemetry_dropped_total=2, event_queue_depth=5)

    async def fake_workers():
        return [WorkerStatus(kind="telemetry-receiver", last_status="ok", runs_total=4)]

    monkeypatch.setattr("app.services.observability.metrics.collect_metrics_snapshot", fake_snapshot)
    monkeypatch.setattr("app.services.observability.metrics.get_all_worker_status", fake_workers)

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/metrics")

    assert resp.status_code == 200
    text = resp.text
    assert "nms_kpi_rows 7.0" in text
    assert "nms_telemetry_raw_rows 3.0" in text
    assert 'nms_worker_stale{kind="telemetry-receiver"} 0.0' in text
