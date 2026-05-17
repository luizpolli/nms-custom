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
        self.group_created = False
        self.acked = []
        self.claimed = []

    async def read_since(self, last_id="0-0", *, count=10, block_ms=1000):
        return self.events

    async def ensure_consumer_group(self, group_name, *, start_id="0-0"):
        self.group_created = True

    async def read_group(self, group_name, consumer_name, *, count=10, block_ms=1000, new_messages_id=">"):
        return self.events

    async def claim_stale(self, group_name, consumer_name, *, min_idle_ms=60000, count=10):
        return self.claimed

    async def ack(self, group_name, *stream_ids):
        self.acked.extend(stream_ids)
        return len(stream_ids)

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
    assert stats.acked == 2
    assert bus.group_created is True
    assert bus.acked == ["1-0", "2-0"]


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


@pytest.mark.asyncio
async def test_consumer_claims_stale_pending_before_new_reads():
    bus = FakeBus([])
    bus.claimed = [("9-0", _event("alarm.created", "evt-9"))]
    consumer = AlarmEventConsumer(bus=bus, group_name="g", consumer_name="c")

    stats = await consumer.poll_once()

    assert stats.claimed == 1
    assert stats.handled == 1
    assert stats.acked == 1
    assert bus.acked == ["9-0"]
