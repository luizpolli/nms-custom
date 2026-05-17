import pytest

from app.services.events import EventEnvelope
from app.services.events.consumers import (
    AlarmEventConsumer,
    DiscoveryEventConsumer,
    TelemetryEventConsumer,
    consumer_for_kind,
)


class FakeBus:
    def __init__(self, events):
        self.events = events
        self.closed = False

    async def read_since(self, last_id="0-0", *, count=10, block_ms=1000):
        return self.events

    async def close(self):
        self.closed = True


def _event(event_type: str, event_id: str = "evt-1") -> EventEnvelope:
    return EventEnvelope(event_type=event_type, source="test", event_id=event_id, payload={"ok": True})


@pytest.mark.asyncio
async def test_alarm_consumer_accepts_alarm_like_events_idempotently():
    consumer = AlarmEventConsumer(bus=FakeBus([]))
    event = _event("alarm.created")

    assert await consumer.process_one("1-0", event) is True
    assert await consumer.process_one("2-0", event) is False

    assert consumer.stats.handled == 1
    assert consumer.stats.skipped == 1


@pytest.mark.asyncio
async def test_consumer_poll_once_skips_unrelated_events():
    bus = FakeBus([("1-0", _event("telemetry.sample")), ("2-0", _event("inventory.updated", "evt-2"))])
    consumer = DiscoveryEventConsumer(bus=bus)

    stats = await consumer.poll_once()

    assert stats.seen == 2
    assert stats.handled == 1
    assert stats.skipped == 1
    assert stats.last_stream_id == "2-0"


@pytest.mark.asyncio
async def test_telemetry_consumer_handles_gnmi_events_and_closes_bus():
    bus = FakeBus([("1-0", _event("gnmi.update"))])
    consumer = TelemetryEventConsumer(bus=bus)

    stats = await consumer.poll_once()
    await consumer.close()

    assert stats.handled == 1
    assert bus.closed is True


def test_consumer_factory_rejects_unknown_kind():
    assert isinstance(consumer_for_kind("worker-alarm"), AlarmEventConsumer)
    with pytest.raises(ValueError):
        consumer_for_kind("nope")
