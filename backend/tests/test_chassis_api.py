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


# ---------------------------------------------------------------------------
# Profile detection — NCS560
# ---------------------------------------------------------------------------


def test_chassis_profile_detects_ncs560_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="ncs560-pe01",
        ip_address="10.0.0.50",
        device_type="router",
        model="Cisco NCS-560-28GT-400G",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs560"


def test_chassis_profile_detects_ncs560_no_dash_variant():
    """Model string without dash — 'NCS560' — must also resolve to ncs560."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs560-pe02",
        ip_address="10.0.0.51",
        device_type="router",
        model="Cisco NCS560",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs560"


# ---------------------------------------------------------------------------
# Profile detection — NCS540
# ---------------------------------------------------------------------------


def test_chassis_profile_detects_ncs540_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-pe01",
        ip_address="10.0.0.55",
        device_type="router",
        model="Cisco NCS-540-24Z8Q2C-SYS",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540"


def test_chassis_profile_detects_ncs540_from_n540_shortname():
    """Short-form 'N540' alias must also resolve to ncs540."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-pe02",
        ip_address="10.0.0.56",
        device_type="router",
        model="Cisco N540-24Z8Q2C-M",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540"


# ---------------------------------------------------------------------------
# Profile detection — NCS540L_CE sub-models (ncs540-16z4, ncs540-12z16g)
# ---------------------------------------------------------------------------


def test_chassis_profile_detects_ncs540_16z4_from_device_model():
    """N540X-16Z4G8Q2C-D must resolve to ncs540-16z4 (not generic ncs540)."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-16z4-pe01",
        ip_address="10.0.0.57",
        device_type="router",
        model="Cisco N540X-16Z4G8Q2C-D",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-16z4"


def test_chassis_profile_detects_ncs540_16z4_from_inventory_model():
    """Detection via Inventory.hardware_model string for N540X-16Z4G8Q2C-D."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-16z4-pe02",
        ip_address="10.0.0.58",
        device_type="router",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device.id,
        hardware_model="N540X-16Z4G8Q2C-D",
    )

    assert _chassis_profile_for_device(device, inventory) == "ncs540-16z4"


def test_chassis_profile_detects_ncs540_12z16g_from_device_model():
    """NCS_540X-12Z16G-SYS-D must resolve to ncs540-12z16g (not generic ncs540)."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-12z16g-pe01",
        ip_address="10.0.0.59",
        device_type="router",
        model="Cisco NCS_540X-12Z16G-SYS-D",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-12z16g"


def test_chassis_profile_detects_ncs540_12z16g_from_inventory_model():
    """Detection via Inventory.hardware_model string for N540X-12Z16G-SYS-D."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-12z16g-pe02",
        ip_address="10.0.0.60",
        device_type="router",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device.id,
        hardware_model="N540X-12Z16G-SYS-D",
    )

    assert _chassis_profile_for_device(device, inventory) == "ncs540-12z16g"


def test_chassis_profile_ncs540_generic_not_stolen_by_submodels():
    """A generic NCS-540 model (no 16Z4 / 12Z16G tokens) must still resolve to ncs540."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-generic-pe01",
        ip_address="10.0.0.61",
        device_type="router",
        model="Cisco NCS-540-24Z8Q2C-SYS",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540"


# ---------------------------------------------------------------------------
# Profile detection — NCS540L_CE additional sub-models (Phase 2)
# ---------------------------------------------------------------------------


def test_chassis_profile_detects_ncs540_28z4c_from_device_model():
    """N540-28Z4C-SYS-D must resolve to ncs540-28z4c."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-28z4c-pe01",
        ip_address="10.0.1.1",
        device_type="router",
        model="Cisco N540-28Z4C-SYS-D",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-28z4c"


def test_chassis_profile_detects_ncs540_28z4c_ac_variant():
    """N540-28Z4C-SYS-A (AC power) must also resolve to ncs540-28z4c."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-28z4c-ac-pe01",
        ip_address="10.0.1.2",
        device_type="router",
        model="Cisco N540-28Z4C-SYS-A",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-28z4c"


def test_chassis_profile_detects_ncs540_12z20g_from_device_model():
    """N540-12Z20G-SYS-D must resolve to ncs540-12z20g."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-12z20g-pe01",
        ip_address="10.0.1.3",
        device_type="router",
        model="Cisco N540-12Z20G-SYS-D",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-12z20g"


def test_chassis_profile_detects_ncs540_12z20g_ac_variant():
    """N540-12Z20G-SYS-A (AC power) must also resolve to ncs540-12z20g."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-12z20g-ac-pe01",
        ip_address="10.0.1.4",
        device_type="router",
        model="Cisco N540-12Z20G-SYS-A",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-12z20g"


def test_chassis_profile_detects_ncs540_fh_agg():
    """N540-FH-AGG-SYS must resolve to ncs540-fh-agg."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-fhagg-pe01",
        ip_address="10.0.1.5",
        device_type="router",
        model="Cisco N540-FH-AGG-SYS",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-fh-agg"


def test_chassis_profile_detects_ncs540_fh_csr():
    """N540-FH-CSR-SYS must resolve to ncs540-fh-csr."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-fhcsr-pe01",
        ip_address="10.0.1.6",
        device_type="router",
        model="Cisco N540-FH-CSR-SYS",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-fh-csr"


def test_chassis_profile_detects_ncs540x_4z14g2q_from_device_model():
    """N540X-4Z14G2Q-D must resolve to ncs540x-4z14g2q."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540x-4z14g2q-pe01",
        ip_address="10.0.1.7",
        device_type="router",
        model="Cisco N540X-4Z14G2Q-D",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540x-4z14g2q"


def test_chassis_profile_detects_ncs540x_4z14g2q_ac_variant():
    """N540X-4Z14G2Q-A (AC power) must also resolve to ncs540x-4z14g2q."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540x-4z14g2q-ac-pe01",
        ip_address="10.0.1.8",
        device_type="router",
        model="Cisco N540X-4Z14G2Q-A",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540x-4z14g2q"


def test_chassis_profile_ncs540_16z4_detects_ac_variant():
    """N540X-16Z4G8Q2C-A (AC power) must map to ncs540-16z4 (same layout as -D)."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-16z4a-pe01",
        ip_address="10.0.1.9",
        device_type="router",
        model="Cisco N540X-16Z4G8Q2C-A",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-16z4"


def test_chassis_profile_ncs540_12z16g_detects_ac_variant():
    """N540X-12Z16G-SYS-A (AC power) must map to ncs540-12z16g (same layout as -D)."""
    device = Device(
        id=uuid.uuid4(),
        name="ncs540-12z16ga-pe01",
        ip_address="10.0.1.10",
        device_type="router",
        model="Cisco N540X-12Z16G-SYS-A",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs540-12z16g"


# ---------------------------------------------------------------------------
# Profile detection — ASR9010
# ---------------------------------------------------------------------------


def test_chassis_profile_detects_asr9010_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-asr9010",
        ip_address="10.0.0.60",
        device_type="router",
        model="Cisco ASR 9010",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "asr9010"


def test_chassis_profile_detects_asr9010_dash_variant():
    """Model 'ASR-9010' (with dash) must also resolve to asr9010."""
    device = Device(
        id=uuid.uuid4(),
        name="core-asr9010-b",
        ip_address="10.0.0.61",
        device_type="router",
        model="Cisco ASR-9010-AC",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "asr9010"


def test_chassis_profile_asr9010_does_not_match_asr9006():
    """Ensure asr9010 and asr9006 detection rules do not cross-match."""
    device9006 = Device(
        id=uuid.uuid4(),
        name="core-asr9006",
        ip_address="10.0.0.20",
        device_type="router",
        model="Cisco ASR 9006",
        vendor="Cisco",
    )
    device9010 = Device(
        id=uuid.uuid4(),
        name="core-asr9010",
        ip_address="10.0.0.21",
        device_type="router",
        model="Cisco ASR 9010",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device9006, None) == "asr9006"
    assert _chassis_profile_for_device(device9010, None) == "asr9010"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_chassis_profile_returns_none_for_device_with_no_model_and_no_inventory():
    device = Device(
        id=uuid.uuid4(),
        name="unknown-device",
        ip_address="10.0.0.99",
        device_type="unknown",
        vendor="Unknown",
    )

    assert _chassis_profile_for_device(device, None) is None


def test_chassis_profile_returns_none_for_unsupported_platform():
    """A Cisco Nexus 9000 string should not match any chassis profile."""
    device = Device(
        id=uuid.uuid4(),
        name="nexus-sw01",
        ip_address="10.0.0.100",
        device_type="switch",
        model="Cisco Nexus 9000",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) is None


def test_chassis_profile_is_case_insensitive_for_ncs55a1():
    """Both lowercase and uppercase model strings must match ncs55a1."""
    device_lower = Device(
        id=uuid.uuid4(),
        name="ncs55a1-lower",
        ip_address="10.0.0.32",
        device_type="router",
        model="cisco ncs-55a1-36h-se-s",
        vendor="Cisco",
    )
    device_upper = Device(
        id=uuid.uuid4(),
        name="ncs55a1-upper",
        ip_address="10.0.0.33",
        device_type="router",
        model="CISCO NCS-55A1-36H-SE-S",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device_lower, None) == "ncs55a1"
    assert _chassis_profile_for_device(device_upper, None) == "ncs55a1"


# ---------------------------------------------------------------------------
# Endpoint tests — NCS55A1 (kept in original position below)
# ---------------------------------------------------------------------------


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


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_ncs560_profile_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="ncs560-pe01",
        ip_address="10.0.0.52",
        device_type="router",
        model="Cisco NCS-560-28GT-400G",
        vendor="Cisco",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["profileId"] == "Cisco_NCS560"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "ncs560-pe01"
    assert len(chassis["views"][0]["hotspots"]) == 55


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_ncs540_profile_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="ncs540-pe01",
        ip_address="10.0.0.57",
        device_type="router",
        model="Cisco NCS-540-24Z8Q2C-SYS",
        vendor="Cisco",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["profileId"] == "Cisco_NCS540"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "ncs540-pe01"
    assert len(chassis["views"][0]["hotspots"]) == 33


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_asr9010_profile_for_supported_device():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="core-asr9010-mx01",
        ip_address="10.0.0.62",
        device_type="router",
        model="Cisco ASR 9010",
        vendor="Cisco",
    )

    chassis = await get_device_chassis(device_id, _FakeSession(device))  # type: ignore[arg-type]

    assert chassis["schemaVersion"] == "nms.chassisView.v1"
    assert chassis["profileId"] == "Cisco_ASR_9010_Router"
    assert chassis["deviceId"] == str(device_id)
    assert chassis["tree"][0]["label"] == "core-asr9010-mx01"
    assert len(chassis["views"][0]["hotspots"]) == 18


# ── NCS55A1 variant detection ─────────────────────────────────────────────────

def test_chassis_profile_detects_ncs55a1_48q6h_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1-48q6h",
        ip_address="10.0.0.70",
        device_type="router",
        model="NCS-55A1-48Q6H",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs55a1-48q6h"


def test_chassis_profile_detects_ncs55a1_24q6h_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1-24q6h",
        ip_address="10.0.0.71",
        device_type="router",
        model="NCS-55A1-24Q6H-S",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs55a1-24q6h"


def test_chassis_profile_detects_ncs55a1_24q6h_ss_variant():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1-24q6h-ss",
        ip_address="10.0.0.72",
        device_type="router",
        model="NCS-55A1-24Q6H-SS",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs55a1-24q6h"


def test_chassis_profile_detects_ncs55a1_24h_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1-24h",
        ip_address="10.0.0.73",
        device_type="router",
        model="NCS-55A1-24H",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs55a1-24h"


def test_chassis_profile_ncs55a1_36h_falls_back_to_generic():
    """NCS-55A1-36H-S / 36H-SE-S should use the generic ncs55a1 profile."""
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs55a1-36h",
        ip_address="10.0.0.74",
        device_type="router",
        model="NCS-55A1-36H-SE-S",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs55a1"


# ── NCS5500 fixed-port router detection ───────────────────────────────────────

def test_chassis_profile_detects_ncs5501_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5501",
        ip_address="10.0.0.75",
        device_type="router",
        model="NCS-5501",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs5501"


def test_chassis_profile_detects_ncs5501_se_variant():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5501-se",
        ip_address="10.0.0.76",
        device_type="router",
        model="NCS-5501-SE",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs5501"


def test_chassis_profile_detects_ncs5502_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5502",
        ip_address="10.0.0.77",
        device_type="router",
        model="NCS-5502",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs5502"


def test_chassis_profile_detects_ncs5502_se_variant():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5502-se",
        ip_address="10.0.0.78",
        device_type="router",
        model="NCS-5502-SE",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs5502"


def test_chassis_profile_detects_ncs5508_from_device_model():
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5508",
        ip_address="10.0.0.79",
        device_type="router",
        model="NCS-5508",
        vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "ncs5508"


def test_chassis_profile_ncs5501_not_confused_with_ncs55a1():
    """Ensure NCS5501 does not accidentally match the ncs55a1 profile."""
    device = Device(
        id=uuid.uuid4(),
        name="core-ncs5501-check",
        ip_address="10.0.0.80",
        device_type="router",
        model="Cisco NCS 5501",
        vendor="Cisco",
    )
    profile = _chassis_profile_for_device(device, None)
    assert profile == "ncs5501"
    assert profile != "ncs55a1"


# ---------------------------------------------------------------------------
# PID-based profile detection (exact entPhysicalModelName mapping)
# ---------------------------------------------------------------------------

from app.api.devices import CHASSIS_PID_PROFILES, _chassis_pid_for_device  # noqa: E402


def _chassis_component(model_name: str, physical_class: int = 3) -> PhysicalInventoryComponent:
    return PhysicalInventoryComponent(
        id=uuid.uuid4(),
        device_id=uuid.uuid4(),
        physical_index=1,
        name="Chassis",
        physical_class=physical_class,
        model_name=model_name,
    )


def test_every_pid_profile_target_is_a_known_profile():
    from app.api.devices import CHASSIS_PROFILE_FILES

    unknown = {p for p in CHASSIS_PID_PROFILES.values() if p not in CHASSIS_PROFILE_FILES}
    assert not unknown, f"PID table maps to missing profiles: {unknown}"


def test_chassis_pid_from_physical_components_wins_over_model_heuristics():
    """A collected chassis PID must beat the device.model substring heuristics."""
    device = Device(
        id=uuid.uuid4(),
        name="mislabeled-router",
        ip_address="10.0.2.1",
        device_type="router",
        model="Cisco ASR 9006",  # heuristics alone would say asr9006
        vendor="Cisco",
    )
    components = [_chassis_component("NCS-55A1-36H-SE-S")]

    assert _chassis_profile_for_device(device, None, components) == "ncs55a1"


def test_chassis_pid_detects_asr920_variant_from_walk_pid():
    """PIDs captured in docs/snmpwalks/asr920 resolve via the exact table."""
    device = Device(
        id=uuid.uuid4(),
        name="edge-920",
        ip_address="10.0.2.2",
        device_type="router",
        vendor="Cisco",
    )
    for pid in ("ASR-920-12CZ-D", "ASR-920-12SZ-D", "ASR-920-12SZ-IM", "ASR-920-12SZ-IM-CC"):
        components = [_chassis_component(pid)]
        assert _chassis_profile_for_device(device, None, components) == "asr920", pid


def test_chassis_pid_detects_ncs560_sys_pid_not_covered_by_heuristics():
    """N560-4-SYS contains no 'ncs560' token, so only the PID table can map it."""
    device = Device(
        id=uuid.uuid4(),
        name="agg-n560",
        ip_address="10.0.2.3",
        device_type="router",
        model="N560-4-SYS",
        vendor="Cisco",
    )

    assert _chassis_profile_for_device(device, None) == "ncs560"


def test_chassis_pid_from_legacy_inventory_json_items():
    """physicalClass may be the label string in legacy inventory JSON blobs."""
    device = Device(
        id=uuid.uuid4(),
        name="legacy-blob",
        ip_address="10.0.2.4",
        device_type="router",
        vendor="Cisco",
    )
    inventory = Inventory(
        id=uuid.uuid4(),
        device_id=device.id,
        additional_info={
            "physical_inventory": [
                {"physicalIndex": 1, "physicalClass": "chassis", "modelName": "N540X-16Z4G8Q2C-A"},
            ]
        },
    )

    assert _chassis_pid_for_device(device, inventory) == "N540X-16Z4G8Q2C-A"
    assert _chassis_profile_for_device(device, inventory) == "ncs540-16z4"


def test_chassis_pid_normalizes_trailing_equals_and_case():
    device = Device(
        id=uuid.uuid4(),
        name="weird-pid",
        ip_address="10.0.2.5",
        device_type="router",
        vendor="Cisco",
    )
    components = [_chassis_component("ncs-5501-se= ")]

    assert _chassis_pid_for_device(device, None, components) == "NCS-5501-SE"
    assert _chassis_profile_for_device(device, None, components) == "ncs5501"


def test_chassis_pid_ignores_non_chassis_components():
    device = Device(
        id=uuid.uuid4(),
        name="no-chassis-row",
        ip_address="10.0.2.6",
        device_type="router",
        vendor="Cisco",
    )
    components = [_chassis_component("A900-IMA8S", physical_class=9)]

    assert _chassis_pid_for_device(device, None, components) is None
    assert _chassis_profile_for_device(device, None, components) is None


@pytest.mark.asyncio
async def test_chassis_endpoint_resolves_profile_from_collected_pid():
    """Endpoint must use persisted physical inventory PID when model is generic."""
    device_id = uuid.uuid4()
    device = Device(
        id=device_id,
        name="pid-resolved",
        ip_address="10.0.2.7",
        device_type="router",
        model="Cisco Router",  # no usable heuristic token
        vendor="Cisco",
    )
    chassis_row = PhysicalInventoryComponent(
        id=uuid.uuid4(),
        device_id=device_id,
        physical_index=1,
        name="Chassis",
        physical_class=3,
        model_name="NCS-55A1-36H-SE-S",
    )

    class _PidSession(_FakeSession):
        async def execute(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _FakeResult(scalar=self.device)
            if self.calls == 2:
                return _FakeResult(rows=self.physical_components)
            return _FakeResult(rows=[])  # alarms query

    chassis = await get_device_chassis(device_id, _PidSession(device, [chassis_row]))  # type: ignore[arg-type]

    assert chassis["profileId"] == "Cisco_NCS55A1"
    assert chassis["source"]["profile"] == "ncs55a1"
