"""Unit tests for WorkerHeartbeat and status aggregation.

Uses an in-memory fake Redis client to avoid requiring a live broker; the
helper itself imports `redis.asyncio` lazily inside `_client()` and reads
`settings.redis_url`, so we monkeypatch the import target.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.observability import heartbeat as hb_mod
from app.services.observability.heartbeat import (
    WORKER_KINDS,
    WorkerHeartbeat,
    WorkerStatus,
    _parse_status,
    get_all_worker_status,
)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, str]] = {}
        self.closed = False

    async def hset(self, key: str, mapping: dict[str, object]) -> None:
        bucket = self.store.setdefault(key, {})
        for k, v in mapping.items():
            bucket[k] = str(v)

    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        bucket = self.store.setdefault(key, {})
        current = int(bucket.get(field, "0"))
        current += amount
        bucket[field] = str(current)
        return current

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.store.get(key, {}))

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def fake_redis(monkeypatch):
    """Patch the `redis.asyncio.from_url` factory used inside the heartbeat module."""
    fake = _FakeAsyncRedis()

    class _FakeModule:
        @staticmethod
        def from_url(*_a, **_kw):
            return fake

    monkeypatch.setitem(__import__("sys").modules, "redis", type("R", (), {"asyncio": _FakeModule}))
    monkeypatch.setitem(__import__("sys").modules, "redis.asyncio", _FakeModule)
    yield fake


@pytest.mark.asyncio
async def test_success_sets_ok_and_increments_runs(fake_redis):
    beat = WorkerHeartbeat("monitoring-policies", expected_interval_s=30)
    await beat.success()
    bucket = fake_redis.store["nms:workers:monitoring-policies"]
    assert bucket["last_status"] == "ok"
    assert bucket["runs_total"] == "1"
    assert bucket["last_error"] == ""
    assert bucket["expected_interval_s"] == "30"


@pytest.mark.asyncio
async def test_failure_sets_error_and_increments_errors(fake_redis):
    beat = WorkerHeartbeat("topology", expected_interval_s=60)
    await beat.failure("snmp timeout")
    bucket = fake_redis.store["nms:workers:topology"]
    assert bucket["last_status"] == "error"
    assert bucket["errors_total"] == "1"
    assert bucket["last_error"] == "snmp timeout"


@pytest.mark.asyncio
async def test_starting_does_not_increment_counters(fake_redis):
    beat = WorkerHeartbeat("trap-receiver", expected_interval_s=60)
    await beat.starting()
    bucket = fake_redis.store["nms:workers:trap-receiver"]
    assert bucket["last_status"] == "starting"
    assert "runs_total" not in bucket
    assert "errors_total" not in bucket


@pytest.mark.asyncio
async def test_get_all_worker_status_returns_every_known_kind(fake_redis):
    beat = WorkerHeartbeat("syslog-receiver", expected_interval_s=60)
    await beat.success()
    statuses = await get_all_worker_status()
    kinds = {s.kind for s in statuses}
    assert set(WORKER_KINDS).issubset(kinds)
    syslog = next(s for s in statuses if s.kind == "syslog-receiver")
    assert syslog.last_status == "ok"
    assert syslog.runs_total == 1
    assert syslog.is_stale is False


def test_parse_status_marks_missing_heartbeat_as_stale():
    status = _parse_status("monitoring-policies", None)
    assert isinstance(status, WorkerStatus)
    assert status.is_stale is True
    assert status.last_status is None


def test_parse_status_detects_old_heartbeat_as_stale():
    old = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    raw = {"last_run_at": old, "expected_interval_s": "30", "last_status": "ok"}
    status = _parse_status("topology", raw)
    assert status.is_stale is True


def test_parse_status_keeps_fresh_heartbeat_alive():
    fresh = datetime.now(timezone.utc).isoformat()
    raw = {"last_run_at": fresh, "expected_interval_s": "30", "last_status": "ok"}
    status = _parse_status("topology", raw)
    assert status.is_stale is False


@pytest.mark.asyncio
async def test_heartbeat_never_raises_when_redis_unavailable(monkeypatch):
    """If `redis.asyncio.from_url` raises, heartbeat methods must swallow it."""

    def _raise(*_a, **_kw):
        raise RuntimeError("redis offline")

    class _BrokenModule:
        from_url = staticmethod(_raise)

    monkeypatch.setitem(__import__("sys").modules, "redis", type("R", (), {"asyncio": _BrokenModule}))
    monkeypatch.setitem(__import__("sys").modules, "redis.asyncio", _BrokenModule)

    beat = WorkerHeartbeat("monitoring-policies", expected_interval_s=30)
    await beat.starting()
    await beat.success()
    await beat.failure("boom")
    await beat.close()


def test_worker_kinds_match_supervisor_loops():
    """Guard against forgetting to register a new worker kind in WORKER_KINDS."""
    expected = {
        "monitoring-policies",
        "topology",
        "trap-receiver",
        "syslog-receiver",
        "report-scheduler",
        "telemetry-receiver",
    }
    assert expected.issubset(set(WORKER_KINDS))


# Touch the module-level reference so an accidental rename triggers an import-time fail.
assert hb_mod.WORKER_KINDS == WORKER_KINDS
