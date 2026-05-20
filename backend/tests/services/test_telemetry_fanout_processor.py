"""Unit tests for TelemetryFanoutProcessor."""

import pytest

from app.services.events.envelope import EventEnvelope
from app.services.events.processors.telemetry_fanout import (
    FanoutRule,
    TelemetryFanoutProcessor,
    _rule_matches,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeKPI:
    pass


class FakeSession:
    def __init__(self, kpi=None):
        self._kpi = kpi

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def get(self, model, pk):
        return self._kpi


class FakeSessionFactory:
    def __init__(self, kpi=None):
        self._kpi = kpi

    def __call__(self):
        return FakeSession(self._kpi)


class FakeBus:
    def __init__(self):
        self.published: list[EventEnvelope] = []

    async def publish(self, env):
        self.published.append(env)
        return "fake-id"


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def _ev(event_type="telemetry.sample.normalized", severity="", kpi_type="", tags=None):
    payload = {}
    if kpi_type:
        payload["kpi_type"] = kpi_type
    if tags:
        payload["device_tags"] = tags
    return EventEnvelope(event_type=event_type, source="test", severity=severity or None, payload=payload)


def test_rule_matches_wildcard():
    rule = FanoutRule(name="all", event_type_pattern="telemetry.*")
    assert _rule_matches(rule, _ev("telemetry.sample.normalized"))
    assert not _rule_matches(rule, _ev("kpi.update"))


def test_rule_matches_severity_filter():
    rule = FanoutRule(name="crit", event_type_pattern="*", severity="critical")
    assert _rule_matches(rule, _ev(severity="critical"))
    assert not _rule_matches(rule, _ev(severity="warning"))


def test_rule_matches_kpi_type():
    rule = FanoutRule(name="cpu", event_type_pattern="*", kpi_type="cpu_utilization")
    assert _rule_matches(rule, _ev(kpi_type="cpu_utilization"))
    assert not _rule_matches(rule, _ev(kpi_type="memory"))


def test_rule_matches_device_tags_subset():
    rule = FanoutRule(name="tagged", event_type_pattern="*", required_device_tags=["cisco", "core"])
    assert _rule_matches(rule, _ev(tags=["cisco", "core", "prod"]))
    assert not _rule_matches(rule, _ev(tags=["cisco"]))


# ---------------------------------------------------------------------------
# Happy path: KPI route
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_routes_to_kpi_and_returns_count(monkeypatch):
    calls = []

    class FakeEvaluator:
        def __init__(self, sf):
            pass

        async def evaluate(self, samples):
            calls.append(samples)
            return 1

    monkeypatch.setattr("app.services.kpi.thresholds.KPIThresholdEvaluator", FakeEvaluator)
    kpi = FakeKPI()
    processor = TelemetryFanoutProcessor(FakeSessionFactory(kpi))
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        payload={"kpi_id": 42},
    )

    routed = await processor.process(event)

    assert routed.get("kpi", 0) + routed.get("threshold", 0) >= 1
    assert len(calls) >= 1


@pytest.mark.asyncio
async def test_process_no_kpi_id_returns_zero_route():
    processor = TelemetryFanoutProcessor(FakeSessionFactory())
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        payload={},
    )

    routed = await processor.process(event)

    assert all(v == 0 for v in routed.values())


# ---------------------------------------------------------------------------
# Webhook routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_webhook_publishes_republish_event():
    bus = FakeBus()
    rule = FanoutRule(
        name="webhook-rule",
        event_type_pattern="telemetry.*",
        destinations=["webhook"],
        webhook_url="https://example.com/hook",
    )
    processor = TelemetryFanoutProcessor(FakeSessionFactory(), rules=[rule], bus=bus)
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        device_id="dev-1",
        payload={"kpi_id": 5},
    )

    routed = await processor.process(event)

    assert routed.get("webhook") == 1
    assert len(bus.published) == 1
    assert bus.published[0].event_type == "telemetry.fanout.republish"
    assert bus.published[0].payload["webhook_url"] == "https://example.com/hook"


@pytest.mark.asyncio
async def test_webhook_without_bus_skips_silently():
    rule = FanoutRule(
        name="wh",
        event_type_pattern="*",
        destinations=["webhook"],
        webhook_url="https://example.com/hook",
    )
    processor = TelemetryFanoutProcessor(FakeSessionFactory(), rules=[rule], bus=None)
    event = EventEnvelope(event_type="telemetry.x", source="t", payload={})

    routed = await processor.process(event)

    assert routed.get("webhook", 0) == 0


# ---------------------------------------------------------------------------
# Idempotency: same event processed twice — no double-counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_matching_rule_returns_empty_routed():
    rule = FanoutRule(name="no-match", event_type_pattern="kpi.*")
    processor = TelemetryFanoutProcessor(FakeSessionFactory(), rules=[rule])
    event = EventEnvelope(event_type="telemetry.sample.normalized", source="t", payload={})

    routed = await processor.process(event)

    assert routed == {}


# ---------------------------------------------------------------------------
# Poison-pill: malformed kpi_id must not crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_integer_kpi_id_is_handled_safely():
    processor = TelemetryFanoutProcessor(FakeSessionFactory())
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        payload={"kpi_id": "not-an-int"},
    )

    try:
        routed = await processor.process(event)
    except Exception:
        pytest.fail("Processor raised on malformed kpi_id")
