"""Tests for normalized chassis-view device helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.api.devices import (
    _apply_physical_inventory_to_chassis,
    _chassis_profile_for_device,
    _customize_chassis_model,
    _upsert_physical_inventory_components,
    get_device_chassis,
)
from app.models.device import Device
from app.models.inventory import Inventory
from app.models.physical_inventory import PhysicalInventoryComponent
from app.services.snmp.engine import PhysicalInventoryRow


class _FakeResult:
    def __init__(self, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = list(rows or [])

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self, device: Device | None, physical_components=None):
        self.device = device
        self.physical_components = list(physical_components or [])
        self.calls = 0
        self.added = []

    async def execute(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return _FakeResult(scalar=self.device)
        return _FakeResult(rows=self.physical_components)

    def add(self, obj):
        self.added.append(obj)


def test_chassis_profile_detects_asr903_from_inventory_model():
    device = Device(
        id=uuid.uuid4(),
        name="edge-asr",
        ip_address="10.0.0.10",
        device_type="router",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device.id,
        hardware_model="Cisco ASR-903 Router",
    )

    assert _chassis_profile_for_device(device, inventory) == "asr903"


def test_chassis_profile_detects_asr9006_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-asr9k",
        ip_address="10.0.0.20",
        device_type="router",
        model="Cisco ASR 9006",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "asr9006"


def test_chassis_profile_detects_asr920_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="edge-asr920",
        ip_address="10.0.0.40",
        device_type="router",
        model="Cisco ASR-920-20SZ-M",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "asr920"


def test_chassis_profile_asr920_takes_priority_over_asr903_keyword_overlap():
    # Ensures the "asr"+"920" branch is evaluated before "asr"+"903".
    device = Device(
        id=uuid.uuid4(),
        name="edge-asr920",
        ip_address="10.0.0.41",
        device_type="router",
        model="Cisco ASR 920",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "asr920"


def test_chassis_profile_detects_ncs55a1_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1",
        ip_address="10.0.0.30",
        device_type="router",
        model="Cisco NCS-55A1-36H-SE-S",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs55a1"


def test_chassis_model_is_customized_for_live_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="asr903-mx01",
        ip_address="10.0.0.11",
        device_type="router",
        model="ASR-903",
        vendor="Cisco",
    )
    inventory = Inventory(id=uuid.uuid4(), device_id=device_id, hardware_model="Cisco ASR 903 Router")
    model = {
        "deviceId": "sample-asr903",
        "platform": "Cisco ASR 903 Router",
        "source": {"type": "sample"},
        "tree": [{"componentId": "component-1", "label": "Sample chassis"}],
        "componentsById": {"component-1": {"name": "Sample chassis", "displayName": "Sample chassis"}},
    }

    customized = _customize_chassis_model(model, device, inventory, "asr903")

    assert customized["deviceId"] == str(device_id)
    assert customized["source"]["profile"] == "asr903"
    assert customized["source"]["deviceName"] == "asr903-mx01"
    assert customized["tree"][0]["label"] == "asr903-mx01"
    assert customized["componentsById"]["component-1"]["displayName"] == "asr903-mx01"
    assert model["deviceId"] == "sample-asr903"


def test_chassis_model_merges_collected_physical_inventory_by_index():
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        additional_info={
            "physical_inventory": [
                {
                    "physicalIndex": 100,
                    "name": "module 0/RSP0 live",
                    "description": "Route switch processor from ENTITY-MIB",
                    "modelName": "A903-RSP1A-55",
                    "serialNumber": "FOC1234ABCD",
                    "manufacturer": "Cisco",
                    "hardwareVersion": "1.2",
                    "containedPhysicalIndex": 1,
                    "isFRUable": True,
                },
                {"physicalIndex": 9999, "name": "unmapped entity"},
            ]
        },
    )
    chassis = {
        "physicalIndexToComponentId": {"100": "component-rsp0"},
        "componentsById": {
            "component-rsp0": {
                "id": "component-rsp0",
                "name": "static rsp",
                "displayName": "static rsp",
                "type": "module",
                "ports": [],
                "childIds": [],
            }
        },
    }

    stats = _apply_physical_inventory_to_chassis(chassis, inventory)

    component = chassis["componentsById"]["component-rsp0"]
    assert stats == {"available": 2, "matched": 1, "unmatched": 1}
    assert component["displayName"] == "module 0/RSP0 live"
    assert component["serialNumber"] == "FOC1234ABCD"
    assert component["manufacturer"] == "Cisco"
    assert component["source"]["type"] == "entity-mib"


def test_chassis_model_marks_entity_mib_source_when_inventory_matches():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="asr903-live",
        ip_address="10.0.0.13",
        device_type="router",
        model="ASR-903",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device_id,
        hardware_model="Cisco ASR 903 Router",
        additional_info={"physical_inventory": [{"physicalIndex": 100, "name": "live rsp"}]},
    )
    model = {
        "deviceId": "sample-asr903",
        "platform": "Cisco ASR 903 Router",
        "source": {"type": "sample"},
        "tree": [{"componentId": "component-1", "label": "Sample chassis"}],
        "componentsById": {"component-1": {"name": "Sample chassis", "displayName": "Sample chassis"}},
        "physicalIndexToComponentId": {"100": "component-1"},
    }

    customized = _customize_chassis_model(model, device, inventory, "asr903")

    assert customized["source"]["type"] == "static-profile+entity-mib"
    assert customized["source"]["physicalInventory"]["matched"] == 1


def test_chassis_model_prefers_physical_inventory_table_rows():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="asr903-live",
        ip_address="10.0.0.13",
        device_type="router",
        model="ASR-903",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device_id,
        hardware_model="Cisco ASR 903 Router",
        additional_info={"physical_inventory": [{"physicalIndex": 100, "name": "legacy json rsp"}]},
    )
    physical_component = PhysicalInventoryComponent(
        id=uuid.uuid4(),
        device_id=device_id,
        physical_index=100,
        name="table rsp",
        serial_number="TABLE123",
    )
    model = {
        "deviceId": "sample-asr903",
        "platform": "Cisco ASR 903 Router",
        "source": {"type": "sample"},
        "tree": [{"componentId": "component-1", "label": "Sample chassis"}],
        "componentsById": {"component-1": {"name": "Sample chassis", "displayName": "Sample chassis"}},
        "physicalIndexToComponentId": {"100": "component-1"},
    }

    customized = _customize_chassis_model(model, device, inventory, "asr903", [physical_component])

    assert customized["componentsById"]["component-1"]["displayName"] == "asr903-live"
    assert customized["componentsById"]["component-1"]["serialNumber"] == "TABLE123"
    assert customized["source"]["physicalInventory"]["matched"] == 1


@pytest.mark.asyncio
async def test_upsert_physical_inventory_components_creates_table_rows():
    device_id = uuid.uuid4()
    session = _FakeSession(None)
    rows = {
        100: PhysicalInventoryRow(
            physical_index=100,
            name="module 0/RSP0",
            serial_number="FOC1234ABCD",
            model_name="A903-RSP1A-55",
            contained_in=1,
            is_fru=True,
        )
    }

    components = await _upsert_physical_inventory_components(  # type: ignore[arg-type]
        session,
        device_id,
        rows,
        datetime.now(),
    )

    assert len(components) == 1
    assert components[0].device_id == device_id
    assert components[0].physical_index == 100
    assert components[0].serial_number == "FOC1234ABCD"
    assert components[0].metadata_json["source"] == "entity-mib"
    assert session.added == components


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_normalized_contract_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="asr903-mx02",
        ip_address="10.0.0.12",
        device_type="router",
        model="Cisco ASR-903",
        vendor="Cisco",
    )
    device.inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device_id,
        hardware_model="Cisco ASR 903 Router",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "asr903-mx02"
    assert chassis["views"][0]["hotspots"]


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_asr9006_profile_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="asr9006-mx01",
        ip_address="10.0.0.21",
        device_type="router",
        model="Cisco ASR 9006",
        vendor="Cisco",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["profileId"] == "Cisco_ASR_9006_Router"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "asr9006-mx01"
    assert len(chassis["views"][0]["hotspots"]) == 11


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_ncs55a1_profile_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="ncs55a1-mx01",
        ip_address="10.0.0.31",
        device_type="router",
        model="Cisco NCS-55A1-36H-SE-S",
        vendor="Cisco",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["profileId"] == "Cisco_NCS55A1"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "ncs55a1-mx01"
    assert len(chassis["views"][0]["hotspots"]) == 44
