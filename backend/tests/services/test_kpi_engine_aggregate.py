"""Tests for KPIEngine.aggregate()'s object_id parameter — needed to chart
one bulkstats instance (e.g. one StarOS servname) at a time instead of
blending every instance under a device+kpi_type into one averaged line."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.services.kpi.engine import KPIEngine


class _FakeResult:
    def fetchall(self):
        return []


class _FakeSession:
    def __init__(self):
        self.executed_sql: list[str] = []
        self.executed_params: list[dict] = []

    async def execute(self, sql, params):
        self.executed_sql.append(str(sql))
        self.executed_params.append(params)
        return _FakeResult()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


def _session_factory(fake: _FakeSession):
    def factory():
        return fake
    return factory


@pytest.mark.asyncio
async def test_aggregate_without_object_id_omits_filter():
    fake = _FakeSession()
    engine = KPIEngine(None, _session_factory(fake))  # type: ignore[arg-type]

    await engine.aggregate(
        device_id=uuid.uuid4(), kpi_type="bulkstats_gtpu_curr_sessions",
        since=datetime.now(UTC), until=datetime.now(UTC), bucket="5m",
    )

    assert "object_id" not in fake.executed_sql[0]
    assert "object_id" not in fake.executed_params[0]


@pytest.mark.asyncio
async def test_aggregate_with_object_id_adds_filter_and_param():
    fake = _FakeSession()
    engine = KPIEngine(None, _session_factory(fake))  # type: ignore[arg-type]

    await engine.aggregate(
        device_id=uuid.uuid4(), kpi_type="bulkstats_gtpu_curr_sessions",
        since=datetime.now(UTC), until=datetime.now(UTC), bucket="5m",
        object_id="PGW-S5",
    )

    assert "object_id = :object_id" in fake.executed_sql[0]
    assert fake.executed_params[0]["object_id"] == "PGW-S5"
