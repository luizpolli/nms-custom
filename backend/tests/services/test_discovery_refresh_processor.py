"""Unit tests for DiscoveryRefreshOrchestrator."""

import time

import pytest

from app.services.events.processors.discovery_refresh import DiscoveryRefreshOrchestrator


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDevice:
    def __init__(self, device_id="dev-1", ip="10.0.0.1"):
        import uuid
        self.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
        self.ip_address = ip


class FakeSession:
    def __init__(self, device=None):
        self._device = device

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def get(self, model, pk):
        return self._device


class FakeSessionFactory:
    def __init__(self, device=None):
        self._device = device

    def __call__(self):
        return FakeSession(self._device)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_maybe_refresh_triggers_and_returns_true(monkeypatch):
    refreshed = []

    async def fake_run(self, device_id):
        refreshed.append(device_id)

    monkeypatch.setattr(DiscoveryRefreshOrchestrator, "_run_refresh", fake_run)
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=0)

    result = await orchestrator.maybe_refresh("dev-aaa", reason="test")

    assert result is True
    assert "dev-aaa" in refreshed


@pytest.mark.asyncio
async def test_maybe_refresh_records_rate_window(monkeypatch):
    async def fake_run(self, device_id):
        pass

    monkeypatch.setattr(DiscoveryRefreshOrchestrator, "_run_refresh", fake_run)
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=0, max_per_minute=3)

    for i in range(3):
        assert await orchestrator.maybe_refresh(f"dev-{i}", reason="test") is True

    result = await orchestrator.maybe_refresh("dev-4", reason="test")
    assert result is False


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_debounce_blocks_rapid_repeat(monkeypatch):
    async def fake_run(self, device_id):
        pass

    monkeypatch.setattr(DiscoveryRefreshOrchestrator, "_run_refresh", fake_run)
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=60)

    assert await orchestrator.maybe_refresh("dev-x") is True
    assert await orchestrator.maybe_refresh("dev-x") is False


@pytest.mark.asyncio
async def test_debounce_different_devices_not_blocked(monkeypatch):
    async def fake_run(self, device_id):
        pass

    monkeypatch.setattr(DiscoveryRefreshOrchestrator, "_run_refresh", fake_run)
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=60)

    assert await orchestrator.maybe_refresh("dev-a") is True
    assert await orchestrator.maybe_refresh("dev-b") is True


# ---------------------------------------------------------------------------
# In-flight dedup (idempotency)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_in_flight_skip(monkeypatch):
    import asyncio

    gate = asyncio.Event()
    started = []

    async def slow_run(self, device_id):
        started.append(device_id)
        await gate.wait()

    monkeypatch.setattr(DiscoveryRefreshOrchestrator, "_run_refresh", slow_run)
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=0)

    task = asyncio.create_task(orchestrator.maybe_refresh("dev-inf"))
    await asyncio.sleep(0)  # yield so task starts

    ok, reason = orchestrator.should_refresh("dev-inf")
    assert not ok
    assert reason == "in_flight"

    gate.set()
    await task


# ---------------------------------------------------------------------------
# Poison-pill: empty device_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_device_id_skipped():
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(), debounce_s=0)
    result = await orchestrator.maybe_refresh("")
    assert result is False


# ---------------------------------------------------------------------------
# _run_refresh does not crash when device is absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_refresh_missing_device_is_safe():
    orchestrator = DiscoveryRefreshOrchestrator(FakeSessionFactory(device=None), debounce_s=0)
    # Should complete without exception
    await orchestrator._run_refresh("aaaaaaaa-0000-0000-0000-000000000001")
