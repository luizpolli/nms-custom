"""Unit tests for AlarmEnrichmentProcessor."""

import uuid
from datetime import datetime, timezone

import pytest

from app.services.events.processors.alarm_enrichment import AlarmEnrichmentProcessor


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeDevice:
    def __init__(self):
        self.id = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
        self.name = "core-rtr-01"
        self.role = "core"
        self.site_id = "SITE-A"
        self.model = "NCS55A1"


class FakeInterface:
    def __init__(self):
        self.name = "GigabitEthernet0/0/0"
        self.description = "Uplink to PE"
        self.oper_status = "up"
        self.admin_status = "up"


class FakeTopoNode:
    def __init__(self, node_id: str, pk: uuid.UUID | None = None):
        self.id = pk or uuid.uuid4()
        self.node_id = node_id
        self.device_id = FakeDevice().id


class FakeTopoLink:
    def __init__(self, source_id: uuid.UUID, target_id: uuid.UUID):
        self.source_node_id = source_id
        self.target_node_id = target_id


class FakeAlarm:
    def __init__(self, device_id=None):
        self.id = uuid.uuid4()
        self.device_id = device_id or FakeDevice().id
        self.raw_varbinds: dict = {}
        self.occurrence_count = 3
        self.last_seen = datetime(2024, 1, 1, tzinfo=timezone.utc)


class FakeResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj

    def scalars(self):
        return self

    def all(self):
        return [self._obj] if self._obj is not None else []


class FakeSession:
    def __init__(self, device=None, iface=None, topo_node=None, topo_links=None):
        self._device = device
        self._iface = iface
        self._topo_node = topo_node
        self._topo_links = topo_links or []
        self.commits = 0
        self._merged = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass

    async def get(self, model, pk):
        from app.models.device import Device
        from app.models.interface import Interface
        if model is Device:
            return self._device
        if model is Interface:
            return self._iface
        return None

    async def execute(self, stmt):
        from app.models.interface import Interface
        from app.models.topology import TopologyLink, TopologyNode

        stmt_str = str(stmt)
        if "interfaces" in stmt_str:
            return FakeResult(self._iface)
        if "topology_nodes" in stmt_str:
            return FakeResult(self._topo_node)
        if "topology_links" in stmt_str:
            class MultiResult:
                def __init__(self, items):
                    self._items = items
                def scalars(self):
                    return self
                def all(self):
                    return self._items
            return MultiResult(self._topo_links)
        return FakeResult(None)

    async def merge(self, obj):
        self._merged = obj
        return obj

    async def commit(self):
        self.commits += 1


class FakeSessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self._session


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_populates_device_and_occurrence():
    device = FakeDevice()
    alarm = FakeAlarm(device_id=device.id)
    session = FakeSession(device=device)
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))

    enrichment = await processor.enrich(alarm)

    assert enrichment["device"]["name"] == "core-rtr-01"
    assert enrichment["device"]["role"] == "core"
    assert enrichment["device"]["site"] == "SITE-A"
    assert enrichment["device"]["model"] == "NCS55A1"
    assert enrichment["prior_occurrences"] == 3
    assert enrichment["last_seen"] is not None


@pytest.mark.asyncio
async def test_enrich_with_if_index_populates_interface():
    device = FakeDevice()
    iface = FakeInterface()
    alarm = FakeAlarm(device_id=device.id)
    session = FakeSession(device=device, iface=iface)
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))

    enrichment = await processor.enrich(alarm, if_index=1)

    assert enrichment["interface"]["name"] == "GigabitEthernet0/0/0"
    assert enrichment["interface"]["description"] == "Uplink to PE"
    assert enrichment["interface"]["oper_status"] == "up"


@pytest.mark.asyncio
async def test_enrich_topology_context():
    device = FakeDevice()
    node_id = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
    peer_id = uuid.UUID("cccccccc-0000-0000-0000-000000000001")
    node = FakeTopoNode("core-rtr-01", pk=node_id)
    peer = FakeTopoNode("agg-sw-01", pk=peer_id)
    link = FakeTopoLink(node_id, peer_id)

    alarm = FakeAlarm(device_id=device.id)

    class TopologySession(FakeSession):
        def __init__(self):
            super().__init__(device=device, topo_node=node)
            self._peer = peer
            self._links = [link]

        async def execute(self, stmt):
            stmt_str = str(stmt)
            if "topology_links" in stmt_str:
                class MultiResult:
                    def __init__(self, items):
                        self._items = items
                    def scalars(self):
                        return self
                    def all(self):
                        return self._items
                return MultiResult(self._links)
            if "topology_nodes" in stmt_str:
                # First call returns main node, second returns peer
                if not hasattr(self, "_node_calls"):
                    self._node_calls = 0
                self._node_calls += 1
                if self._node_calls == 1:
                    return FakeResult(node)
                return FakeResult(self._peer)
            return FakeResult(None)

    session = TopologySession()
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))
    enrichment = await processor.enrich(alarm)
    assert "topology" in enrichment


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_idempotent_skips_second_call():
    device = FakeDevice()
    alarm = FakeAlarm(device_id=device.id)
    alarm.raw_varbinds = {"_enrichment": {"device": {"name": "already-done"}}}
    session = FakeSession(device=device)
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))

    enrichment = await processor.enrich(alarm)

    assert enrichment["device"]["name"] == "already-done"
    assert session.commits == 0


# ---------------------------------------------------------------------------
# Poison-pill resilience
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrich_no_device_id_returns_empty():
    alarm = FakeAlarm(device_id=None)
    session = FakeSession(device=None)
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))

    enrichment = await processor.enrich(alarm)

    assert enrichment.get("device") is None
    assert "prior_occurrences" in enrichment


@pytest.mark.asyncio
async def test_enrich_missing_device_row_is_safe():
    alarm = FakeAlarm(device_id=uuid.uuid4())
    session = FakeSession(device=None)
    processor = AlarmEnrichmentProcessor(FakeSessionFactory(session))

    enrichment = await processor.enrich(alarm)

    assert "device" not in enrichment
    assert "prior_occurrences" in enrichment
