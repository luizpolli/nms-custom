"""Tests for the object_id filtering added to /performance/devices/{id}/kpis
and the new /kpis/series endpoint — both needed so a single device with
multiple bulkstats instances (e.g. several StarOS servname contexts) can be
charted one series at a time instead of blending them together."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.kpi import KPI


def _kpi(device_id: uuid.UUID, *, kpi_type: str, object_id: str | None, value: float) -> KPI:
    return KPI(
        id=1,
        device_id=device_id,
        kpi_type=kpi_type,
        metric_name=kpi_type,
        value=value,
        source_type="bulkstats",
        object_type="bulkstats-instance",
        object_id=object_id,
        quality="good",
        timestamp=datetime.now(UTC),
    )


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows: list[KPI]):
        self._rows = rows

    async def execute(self, stmt):
        rows = list(self._rows)
        for col, val in self._filters(stmt):
            rows = [r for r in rows if getattr(r, col, None) == val]
        if getattr(stmt, "_distinct", False):
            cols = [d["name"] for d in stmt.column_descriptions]
            seen: list[tuple] = []
            for r in rows:
                key = tuple(getattr(r, c, None) for c in cols)
                if key not in seen:
                    seen.append(key)
            return _FakeResult(seen)
        return _FakeResult(rows)

    @staticmethod
    def _filters(stmt):
        clause = stmt.whereclause
        if clause is None:
            return []
        conditions = list(clause.clauses) if hasattr(clause, "clauses") else [clause]
        out = []
        for cond in conditions:
            if not hasattr(cond, "left") or not hasattr(cond, "right"):
                continue
            name = getattr(cond.left, "name", None) or getattr(cond.left, "key", None)
            value = getattr(cond.right, "value", None)
            if name and value is not None:
                out.append((name, value))
        return out

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_client(rows: list[KPI]) -> TestClient:
    async def _fake_db() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(rows)

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app, raise_server_exceptions=True)


class TestObjectIdFiltering:
    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_list_kpis_filters_by_object_id(self):
        device_id = uuid.uuid4()
        rows = [
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S5", value=100.0),
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S6", value=200.0),
        ]
        client = _make_client(rows)

        resp = client.get(f"/api/performance/devices/{device_id}/kpis", params={"object_id": "PGW-S5"})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["object_id"] == "PGW-S5"
        assert body[0]["value"] == 100.0

    def test_list_kpis_without_object_id_returns_all_instances(self):
        device_id = uuid.uuid4()
        rows = [
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S5", value=100.0),
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S6", value=200.0),
        ]
        client = _make_client(rows)

        resp = client.get(f"/api/performance/devices/{device_id}/kpis")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_kpi_series_returns_distinct_object_ids(self):
        device_id = uuid.uuid4()
        rows = [
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S5", value=100.0),
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S5", value=110.0),
            _kpi(device_id, kpi_type="bulkstats_gtpu_curr_sessions", object_id="PGW-S6", value=200.0),
        ]
        client = _make_client(rows)

        resp = client.get(
            f"/api/performance/devices/{device_id}/kpis/series",
            params={"kpi_type": "bulkstats_gtpu_curr_sessions"},
        )
        assert resp.status_code == 200
        assert sorted(resp.json()) == ["PGW-S5", "PGW-S6"]
