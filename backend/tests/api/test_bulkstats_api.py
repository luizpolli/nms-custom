"""Tests for the bulkstats counter catalog + ingestion-stats API."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.bulkstats import BulkstatsCounterCatalog, BulkstatsIngestionStat


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []

    def scalar_one_or_none(self):
        return self._value


def _matches(row, clause) -> bool:
    """Evaluate a simple equality WHERE clause (optionally AND-combined)
    against one row — covers the `==`/`.is_()` filters used in this API."""
    if clause is None:
        return True
    if hasattr(clause, "clauses"):  # BooleanClauseList — treat as AND
        return all(_matches(row, c) for c in clause.clauses)
    left_name = getattr(clause.left, "name", None) or getattr(clause.left, "key", None) or ""
    right_class = type(clause.right).__name__
    if right_class == "True_":
        right_value: object = True
    elif right_class == "False_":
        right_value = False
    else:
        right_value = getattr(clause.right, "value", None)
    return getattr(row, left_name, None) == right_value


class FakeSession:
    """In-memory store keyed by id, mirroring test_settings_admin.py's pattern."""

    def __init__(self, store: dict):
        self._store = store
        self._pending_conflict: BulkstatsCounterCatalog | None = None

    async def get(self, model_cls, key):
        return self._store.get(key)

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        rows = [v for v in self._store.values() if isinstance(v, entity) and _matches(v, stmt.whereclause)]

        def sort_key(row):
            if entity is BulkstatsCounterCatalog:
                return (row.group, row.field_name)
            return getattr(row, "updated_at", None)

        rows.sort(key=sort_key, reverse=(entity is BulkstatsIngestionStat))
        return _FakeResult(rows)

    def add(self, obj):
        # Column defaults (default=uuid.uuid4 / default=now_utc) only apply
        # on a real SQLAlchemy flush, not on plain construction — fill them
        # in here so this fake behaves like a flushed row would.
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        if getattr(obj, "created_at", None) is None and hasattr(obj, "created_at"):
            obj.created_at = datetime.now(UTC)
        if getattr(obj, "updated_at", None) is None and hasattr(obj, "updated_at"):
            obj.updated_at = datetime.now(UTC)
        if isinstance(obj, BulkstatsCounterCatalog) and any(
            isinstance(existing, BulkstatsCounterCatalog)
            and existing.group == obj.group
            and existing.field_name == obj.field_name
            for existing in self._store.values()
        ):
            # Real SQLAlchemy only raises this on flush, not on add() —
            # defer so the endpoint's try/except around `await db.flush()`
            # actually has something to catch.
            self._pending_conflict = obj
            return
        self._store[obj.id] = obj

    async def flush(self):
        if self._pending_conflict is not None:
            from sqlalchemy.exc import IntegrityError

            self._pending_conflict = None
            raise IntegrityError("duplicate", None, BaseException())

    async def refresh(self, obj):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _make_client(store: dict) -> TestClient:
    async def _fake_db() -> AsyncGenerator[FakeSession, None]:
        yield FakeSession(store)

    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app, raise_server_exceptions=True)


class TestBulkstatsCatalogApi:
    def setup_method(self):
        self.store: dict = {}
        self.client = _make_client(self.store)

    def teardown_method(self):
        app.dependency_overrides.pop(get_db, None)

    def test_list_catalog_empty(self):
        resp = self.client.get("/api/bulkstats/catalog")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_then_list_catalog_entry(self):
        payload = {
            "group": "gtpu",
            "field_name": "curr-sess",
            "metric_name": "bulkstats_gtpu_curr_sessions",
            "object_type": "bulkstats-instance",
            "enabled": True,
        }
        resp = self.client.post("/api/bulkstats/catalog", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["metric_name"] == "bulkstats_gtpu_curr_sessions"
        assert body["enabled"] is True

        listed = self.client.get("/api/bulkstats/catalog").json()
        assert len(listed) == 1
        assert listed[0]["field_name"] == "curr-sess"

    def test_create_duplicate_group_field_name_conflicts(self):
        payload = {
            "group": "gtpu", "field_name": "curr-sess", "metric_name": "m1",
        }
        first = self.client.post("/api/bulkstats/catalog", json=payload)
        assert first.status_code == 201
        second = self.client.post("/api/bulkstats/catalog", json={**payload, "metric_name": "m2"})
        assert second.status_code == 409

    def test_list_catalog_filters_by_enabled_and_group(self):
        self.client.post("/api/bulkstats/catalog", json={
            "group": "gtpu", "field_name": "curr-sess", "metric_name": "m1", "enabled": True,
        })
        self.client.post("/api/bulkstats/catalog", json={
            "group": "saegw", "field_name": "disc-reason-0", "metric_name": "m2", "enabled": False,
        })
        only_enabled = self.client.get("/api/bulkstats/catalog", params={"enabled": True}).json()
        assert {row["group"] for row in only_enabled} == {"gtpu"}

        only_saegw = self.client.get("/api/bulkstats/catalog", params={"group": "saegw"}).json()
        assert {row["field_name"] for row in only_saegw} == {"disc-reason-0"}

    def test_patch_toggle_enabled(self):
        created = self.client.post("/api/bulkstats/catalog", json={
            "group": "gtpu", "field_name": "curr-sess", "metric_name": "m1", "enabled": True,
        }).json()

        resp = self.client.patch(f"/api/bulkstats/catalog/{created['id']}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_unknown_id_returns_404(self):
        resp = self.client.patch(f"/api/bulkstats/catalog/{uuid.uuid4()}", json={"enabled": False})
        assert resp.status_code == 404

    def test_list_ingestion_stats(self):
        stat = BulkstatsIngestionStat(
            source_ip="10.0.0.1", files_processed=3, lines_parsed=100, lines_failed=2,
            unmatched_device=False,
        )
        FakeSession(self.store).add(stat)
        resp = self.client.get("/api/bulkstats/ingestion-stats")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["source_ip"] == "10.0.0.1"
        assert body[0]["files_processed"] == 3
