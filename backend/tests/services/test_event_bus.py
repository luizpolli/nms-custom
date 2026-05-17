"""Tests for canonical event envelope and Redis Streams bus helpers."""

from __future__ import annotations

import json

import pytest

from app.services.events import EventBus, EventEnvelope, publish_event


class FakeRedis:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, str]]] = []
        self.closed = False

    async def xadd(self, stream_name, fields, maxlen=None, approximate=True):
        stream_id = f"{len(self.rows) + 1}-0"
        self.rows.append((stream_id, dict(fields)))
        return stream_id

    async def xrevrange(self, stream_name, count=100):
        return list(reversed(self.rows[-count:]))

    async def aclose(self):
        self.closed = True


def test_event_envelope_defaults_and_roundtrip():
    event = EventEnvelope(
        event_type="linkDown",
        source="snmp_trap",
        severity="major",
        object_type="interface",
        object_id="Gi0/1",
        payload={"source_host": "10.0.0.1"},
    )

    assert event.event_id
    assert event.trace_id == event.event_id
    assert event.timestamp
    assert event.to_dict()["payload"]["source_host"] == "10.0.0.1"

    restored = EventEnvelope.from_dict(event.to_dict())
    assert restored.event_id == event.event_id
    assert restored.event_type == "linkDown"
    assert restored.payload == {"source_host": "10.0.0.1"}


@pytest.mark.asyncio
async def test_event_bus_publish_and_read_latest():
    fake = FakeRedis()
    bus = EventBus(redis_url="redis://example/0", stream_name="test:events")
    bus._redis = fake

    stream_id = await bus.publish(EventEnvelope(event_type="syslog", source="syslog", payload={"msg": "x"}))

    assert stream_id == "1-0"
    stored = fake.rows[0][1]
    assert stored["event_type"] == "syslog"
    assert json.loads(stored["event"])["payload"] == {"msg": "x"}

    events = await bus.read_latest()
    assert len(events) == 1
    assert events[0][0] == "1-0"
    assert events[0][1].event_type == "syslog"
    assert events[0][1].payload == {"msg": "x"}


@pytest.mark.asyncio
async def test_publish_event_skips_when_disabled_in_tests(monkeypatch):
    class ExplodingBus:
        async def publish(self, envelope):  # pragma: no cover - should not be called
            raise AssertionError("publish should be skipped in APP_ENV=test")

        async def close(self):  # pragma: no cover - should not be called
            raise AssertionError("close should be skipped in APP_ENV=test")

    result = await publish_event(EventEnvelope(event_type="x", source="test"), bus=ExplodingBus())
    assert result is None
