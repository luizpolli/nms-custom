"""Tests for the bulkstats ingestion orchestrator.

Uses a small fake AsyncSession (same pattern as tests/api/test_settings_admin.py
and tests/api/test_routes_smoke.py) rather than a real engine: Device's `tags`
ARRAY column doesn't compile on SQLite, and the real Postgres/Timescale
instance is only reachable from inside the Docker network, not a host pytest
run. This tests ingest_file's orchestration logic in isolation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.models.bulkstats import BulkstatsCounterCatalog, BulkstatsIngestionStat
from app.models.device import Device
from app.services.bulkstats.ingest import _build_object_id, ingest_file

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "bulkstats" / "sample_21.25.csv"


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value if isinstance(self._value, list) else []


class FakeSession:
    """Routes select() by target entity class; records everything added."""

    def __init__(self, *, device: Device | None, catalog: list[BulkstatsCounterCatalog]):
        self._device = device
        self._catalog = catalog
        self._stats: dict[str, BulkstatsIngestionStat] = {}
        self.added: list = []

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        if entity is Device:
            return _FakeResult(self._device)
        if entity is BulkstatsCounterCatalog:
            return _FakeResult(list(self._catalog))
        if entity is BulkstatsIngestionStat:
            # Only one source_ip is ever queried per test here.
            return _FakeResult(next(iter(self._stats.values()), None))
        raise AssertionError(f"Unexpected query target: {entity}")

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, BulkstatsIngestionStat):
            self._stats[obj.source_ip] = obj

    def add_all(self, objs):
        for obj in objs:
            self.add(obj)


def test_build_object_id_prefers_servname():
    assert _build_object_id({"vpnname": "SAEGW", "servname": "PGW-S5"}) == "PGW-S5"


def test_build_object_id_falls_back_to_first_label():
    assert _build_object_id({"card": "CPU-1"}) == "CPU-1"


def test_build_object_id_none_when_no_labels():
    assert _build_object_id({}) is None


def test_build_object_id_truncates_oversized_label():
    # Real StarOS field seen in production: disc-reason-summary is a ~500-char
    # packed "code=count;code=count..." blob, not a short identifier — must
    # never blow past the object_id column's 255-char limit.
    blob = "0=1477;1=2341339;" + ("9=1;" * 200)
    assert len(blob) > 255
    result = _build_object_id({"disc-reason-summary": blob})
    assert result == blob[:255]
    assert len(result) == 255


@pytest.mark.asyncio
async def test_ingest_file_matched_device_promotes_enabled_counter():
    device = Device(id=uuid.uuid4(), name="lab-pgw-01", ip_address="10.0.0.1", device_type="staros")
    catalog = [
        BulkstatsCounterCatalog(
            group="gtpu", field_name="curr-sess", metric_name="gtpu_curr_sessions",
            unit=None, object_type="bulkstats-instance", enabled=True,
        )
    ]
    session = FakeSession(device=device, catalog=catalog)

    result = await ingest_file(session, filename="sample_21.25.csv", content=_FIXTURE.read_text())

    assert result.device_id == device.id
    assert result.unmatched_device is False
    assert result.lines_parsed == 2
    assert result.lines_failed == 1
    assert result.raw_samples_written > 0

    # Only the catalog-enabled (gtpu, curr-sess) counter gets promoted to kpis.
    assert result.kpis_promoted == 1
    promoted = next(o for o in session.added if type(o).__name__ == "KPI")
    assert promoted.metric_name == "gtpu_curr_sessions"
    assert promoted.source_type == "bulkstats"
    assert promoted.device_id == device.id

    stat = next(o for o in session.added if isinstance(o, BulkstatsIngestionStat))
    assert stat.files_processed == 1
    assert stat.lines_parsed == 2
    assert stat.lines_failed == 1
    assert stat.unmatched_device is False
    assert stat.last_error  # the truncated cardSch1 line's error message


@pytest.mark.asyncio
async def test_ingest_file_unmatched_device_still_stores_raw_samples():
    session = FakeSession(device=None, catalog=[])

    result = await ingest_file(session, filename="sample_21.25.csv", content=_FIXTURE.read_text())

    assert result.device_id is None
    assert result.unmatched_device is True
    assert result.raw_samples_written > 0
    assert result.kpis_promoted == 0

    stat = next(o for o in session.added if isinstance(o, BulkstatsIngestionStat))
    assert stat.unmatched_device is True
