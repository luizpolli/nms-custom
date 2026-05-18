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
        self.published = []

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

    async def publish(self, envelope):
        self.published.append(envelope)
        return "fake-stream-id"

    async def close(self):
        self.closed = True


def _event(event_type: str, event_id: str = "evt-1") -> EventEnvelope:
    return EventEnvelope(event_type=event_type, source="test", event_id=event_id, payload={"ok": True})


class FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


class FakeSession:
    def __init__(self, get_obj=None):
        self.get_obj = get_obj
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, model, obj_id):
        return self.get_obj

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_alarm_consumer_accepts_alarm_like_events_idempotently():
    consumer = AlarmEventConsumer(bus=FakeBus([]))
    event = _event("alarm.created")

    assert await consumer.process_one("1-0", event) is True
    assert await consumer.process_one("2-0", event) is False

    assert consumer.stats.handled == 1
    assert consumer.stats.skipped == 1


@pytest.mark.asyncio
async def test_alarm_consumer_accepts_syslog_source_even_with_numeric_event_type():
    consumer = AlarmEventConsumer(bus=FakeBus([]), session_factory=FakeSessionFactory(FakeSession()))
    event = EventEnvelope(event_type="16", source="syslog", event_id="evt-syslog", payload={})

    assert await consumer.process_one("1-0", event) is True
    assert consumer.stats.handled == 1


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


@pytest.mark.asyncio
async def test_telemetry_consumer_evaluates_normalized_sample_thresholds(monkeypatch):
    calls = []
    kpi = object()

    class FakeEvaluator:
        def __init__(self, session_factory):
            self.session_factory = session_factory

        async def evaluate(self, samples):
            calls.append(samples)
            return 1

    monkeypatch.setattr("app.services.kpi.thresholds.KPIThresholdEvaluator", FakeEvaluator)
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        event_id="evt-kpi",
        payload={"kpi_id": 123},
    )
    consumer = TelemetryEventConsumer(bus=FakeBus([]), session_factory=FakeSessionFactory(FakeSession(kpi)))

    assert await consumer.process_one("1-0", event) is True
    assert calls == [[kpi]]


@pytest.mark.asyncio
async def test_discovery_consumer_updates_device_status_by_id():
    import uuid as _uuid

    class DeviceObj:
        id = _uuid.UUID("54f0cf75-6d50-4064-9ae4-d169552a71ce")
        status = "unknown"
        updated_at = None

    device = DeviceObj()
    event = EventEnvelope(
        event_type="discovery.device_seen",
        source="discovery",
        device_id="54f0cf75-6d50-4064-9ae4-d169552a71ce",
        payload={"status": "up"},
    )
    session = FakeSession(device)
    consumer = DiscoveryEventConsumer(bus=FakeBus([]), session_factory=FakeSessionFactory(session))

    assert await consumer.process_one("1-0", event) is True
    assert device.status == "up"
    assert device.updated_at is not None
    assert session.commits == 1


@pytest.mark.asyncio
async def test_alarm_consumer_enriches_alarm_with_known_device(monkeypatch):
    class AlarmObj:
        device_id = None
        object_type = None
        object_id = None
        source_type = "trap"

    class DeviceObj:
        id = "device-1"

    alarm = AlarmObj()
    device = DeviceObj()
    session = FakeSession()
    consumer = AlarmEventConsumer(bus=FakeBus([]), session_factory=FakeSessionFactory(session))

    async def fake_find_alarm(*args, **kwargs):
        return alarm

    async def fake_find_device(*args, **kwargs):
        return device

    monkeypatch.setattr(consumer, "_find_alarm", fake_find_alarm)
    monkeypatch.setattr(consumer, "_find_device", fake_find_device)
    event = EventEnvelope(
        event_type="syslog.link_down",
        source="syslog",
        object_id="syslog:mock:%LINK-3-UPDOWN",
        payload={"source_host": "10.255.0.10"},
    )

    assert await consumer.process_one("1-0", event) is True
    assert alarm.device_id == "device-1"
    assert alarm.object_type == "device"
    assert alarm.object_id == "device-1"
    assert alarm.source_type == "syslog"
    assert session.commits == 1


# ---- Phase 5K: Discovery refresh trigger tests ----

@pytest.mark.asyncio
async def test_discovery_consumer_emits_refresh_when_device_becomes_up():
    """A device flipping from down->up must publish discovery.refresh.requested."""
    import uuid

    class DeviceObj:
        id = uuid.UUID("54f0cf75-6d50-4064-9ae4-d169552a71ce")
        status = "down"
        updated_at = None

    device = DeviceObj()
    bus = FakeBus([])
    session = FakeSession(device)
    consumer = DiscoveryEventConsumer(bus=bus, session_factory=FakeSessionFactory(session))

    event = EventEnvelope(
        event_type="discovery.device.status",
        source="discovery",
        device_id="54f0cf75-6d50-4064-9ae4-d169552a71ce",
        payload={"status": "up"},
    )

    assert await consumer.process_one("1-0", event) is True
    assert device.status == "up"
    refresh_events = [e for e in bus.published if e.event_type == "discovery.refresh.requested"]
    assert len(refresh_events) == 1
    assert refresh_events[0].payload["device_id"] == "54f0cf75-6d50-4064-9ae4-d169552a71ce"
    assert "down->up" in refresh_events[0].payload["reason"]


@pytest.mark.asyncio
async def test_discovery_consumer_no_refresh_when_status_unchanged():
    """A device already up that receives another 'up' event must NOT re-emit the refresh."""
    import uuid

    class DeviceObj:
        id = uuid.UUID("54f0cf75-6d50-4064-9ae4-d169552a71ce")
        status = "up"
        updated_at = None

    device = DeviceObj()
    bus = FakeBus([])
    session = FakeSession(device)
    consumer = DiscoveryEventConsumer(bus=bus, session_factory=FakeSessionFactory(session))
    # Pre-seed last_status so the consumer already knows device is up
    consumer._last_status["54f0cf75-6d50-4064-9ae4-d169552a71ce"] = "up"

    event = EventEnvelope(
        event_type="discovery.device.status",
        source="discovery",
        device_id="54f0cf75-6d50-4064-9ae4-d169552a71ce",
        payload={"status": "up"},
    )

    assert await consumer.process_one("1-0", event) is True
    refresh_events = [e for e in bus.published if e.event_type == "discovery.refresh.requested"]
    assert len(refresh_events) == 0


# ---- Phase 5K: Telemetry fan-out tests ----

@pytest.mark.asyncio
async def test_telemetry_consumer_emits_kpi_evaluated_fan_out(monkeypatch):
    """After threshold evaluation, a telemetry.kpi.evaluated fan-out event must be published."""
    kpi = object()

    class FakeEvaluator:
        def __init__(self, session_factory):
            pass

        async def evaluate(self, samples):
            return 0  # no TCAs — severity should be 'nominal'

    monkeypatch.setattr("app.services.kpi.thresholds.KPIThresholdEvaluator", FakeEvaluator)
    bus = FakeBus([])
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        event_id="evt-fanout",
        device_id="dev-abc",
        payload={"kpi_id": 42, "value": 3.14},
    )
    consumer = TelemetryEventConsumer(bus=bus, session_factory=FakeSessionFactory(FakeSession(kpi)))

    assert await consumer.process_one("1-0", event) is True
    fan_outs = [e for e in bus.published if e.event_type == "telemetry.kpi.evaluated"]
    assert len(fan_outs) == 1
    fo = fan_outs[0]
    assert fo.payload["kpi_id"] == 42
    assert fo.payload["device_id"] == "dev-abc"
    assert fo.payload["value"] == 3.14
    assert fo.payload["severity"] == "nominal"
    assert fo.severity == "nominal"


@pytest.mark.asyncio
async def test_telemetry_consumer_emits_warning_severity_on_tca(monkeypatch):
    """When threshold evaluator returns >0 TCAs, fan-out severity must be 'warning'."""
    kpi = object()

    class FakeEvaluator:
        def __init__(self, session_factory):
            pass

        async def evaluate(self, samples):
            return 2  # two TCAs fired

    monkeypatch.setattr("app.services.kpi.thresholds.KPIThresholdEvaluator", FakeEvaluator)
    bus = FakeBus([])
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        event_id="evt-tca",
        device_id="dev-xyz",
        payload={"kpi_id": 7, "value": 99.9},
    )
    consumer = TelemetryEventConsumer(bus=bus, session_factory=FakeSessionFactory(FakeSession(kpi)))

    assert await consumer.process_one("1-0", event) is True
    fan_outs = [e for e in bus.published if e.event_type == "telemetry.kpi.evaluated"]
    assert len(fan_outs) == 1
    assert fan_outs[0].payload["severity"] == "warning"
    assert fan_outs[0].severity == "warning"


@pytest.mark.asyncio
async def test_telemetry_consumer_no_fan_out_when_kpi_not_found():
    """When the KPI row is absent, no fan-out event should be published."""
    bus = FakeBus([])
    event = EventEnvelope(
        event_type="telemetry.sample.normalized",
        source="telemetry",
        event_id="evt-no-kpi",
        payload={"kpi_id": 999},
    )
    # session.get returns None → KPI not found
    consumer = TelemetryEventConsumer(bus=bus, session_factory=FakeSessionFactory(FakeSession(None)))

    assert await consumer.process_one("1-0", event) is True
    fan_outs = [e for e in bus.published if e.event_type == "telemetry.kpi.evaluated"]
    assert len(fan_outs) == 0
