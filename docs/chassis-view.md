# Chassis View — Developer Guide

This document explains how the chassis-view feature works, how to add a new platform profile, and how the full pipeline from SNMP walk to rendered chassis view operates.

---

## Table of Contents

1. [Overview](#overview)
2. [Supported Profiles](#supported-profiles)
3. [Profile Detection Logic](#profile-detection-logic)
4. [The `normalized.json` Schema](#the-normalizedjson-schema)
5. [Adding a New Chassis Profile](#adding-a-new-chassis-profile)
6. [SNMP Walk → Profile Pipeline](#snmp-walk--profile-pipeline)
7. [API Contract](#api-contract)

---

## Overview

The chassis view feature renders an interactive front-panel diagram of a network device. Each supported platform has a **chassis profile** — a pair of files:

| File | Location | Purpose |
|------|----------|---------|
| `normalized.json` | `backend/app/data/chassis/<profile>/` | Component tree, hotspot coordinates, physical index mapping |
| `*.svg` | `frontend/public/chassis-assets/<profile>/` | SVG artwork for the front panel |

The backend loads `normalized.json`, merges live ENTITY-MIB data collected via SNMP, and returns a normalized response that the frontend renders on top of the SVG.

---

## Supported Profiles

| Profile ID | Detection Keywords | `profileId` in JSON | Hotspots |
|------------|-------------------|---------------------|----------|
| `asr903` | `asr` + `903` | `Cisco_ASR903_Router` | varies |
| `asr9006` | `asr` + `9006` | `Cisco_ASR_9006_Router` | 11 |
| `asr9010` | `asr` + `9010` | `Cisco_ASR_9010_Router` | 18 |
| `asr920` | `asr` + `920` | `Cisco_ASR920_Router` | varies |
| `ncs55a1` | `ncs55a1` (compact) | `Cisco_NCS55A1` | 44 |
| `ncs560` | `ncs560` (compact) | `Cisco_NCS560` | 55 |
| `ncs540` | `ncs540` or `n540` (compact) | `Cisco_NCS540` | 33 |

> **Compact** means the detection string is checked after all spaces, dashes, and underscores are removed (e.g. `"NCS-55A1"` → `"ncs55a1"`).

---

## Profile Detection Logic

Detection is implemented in `_chassis_profile_for_device()` in `backend/app/api/devices.py`.

```python
def _chassis_profile_for_device(device: Device, inventory: Inventory | None) -> str | None:
    terms = _device_inventory_terms(device, inventory)   # lowercased, dashes→spaces
    compact_terms = terms.replace(" ", "")               # no spaces at all
    if "ncs55a1" in compact_terms:  return "ncs55a1"
    if "ncs560"  in compact_terms:  return "ncs560"
    if "ncs540"  in compact_terms or "n540" in compact_terms:  return "ncs540"
    if "asr" in terms and "920"  in terms:  return "asr920"
    if "asr" in terms and "903"  in terms:  return "asr903"
    if "asr" in terms and "9006" in terms:  return "asr9006"
    if "asr" in terms and "9010" in terms:  return "asr9010"
    return None
```

**Input terms** are assembled from:
- `device.name`, `device.device_type`, `device.model`, `device.platform_family`, `device.vendor`
- `inventory.hardware_model`, `inventory.serial_number`
- `inventory.additional_info` keys: `model`, `platform`, `platformId`, `device_type`, `product_name`, `chassis_model`

All text is lowercased and dashes/underscores replaced with spaces before matching, so detection is **case-insensitive** and **dash/underscore-insensitive**.

### Priority Order

Rules are evaluated top-to-bottom. NCS platforms are checked first (compact match), then ASR platforms (keyword pair match). This prevents false positives between overlapping model strings.

---

## The `normalized.json` Schema

```jsonc
{
  "schemaVersion": "nms.chassisView.v1",
  "profileId": "Cisco_NCS55A1",          // unique string identifier for the profile
  "platform": "Cisco NCS 55A1",          // human-readable platform name
  "source": { "type": "sample" },        // overwritten at runtime with live data info

  // ── Component tree ────────────────────────────────────────────────────────
  "tree": [
    {
      "componentId": "chassis-root",     // references componentsById key
      "label": "NCS-55A1",               // overwritten at runtime with device name
      "children": [
        { "componentId": "slot-0", "label": "Slot 0", "children": [] }
      ]
    }
  ],

  // ── Component detail map ──────────────────────────────────────────────────
  "componentsById": {
    "chassis-root": {
      "id": "chassis-root",
      "name": "NCS-55A1 Chassis",
      "displayName": "NCS-55A1 Chassis",  // overwritten at runtime with device name
      "type": "chassis",                  // chassis | module | port | fan | psu
      "ports": [],
      "childIds": ["slot-0"]
    },
    "slot-0": {
      "id": "slot-0",
      "name": "slot 0",
      "displayName": "slot 0",
      "type": "module",
      "ports": [],
      "childIds": [],
      // These fields are populated at runtime from ENTITY-MIB:
      // "serialNumber": "...",
      // "modelName": "...",
      // "manufacturer": "...",
      // "hardwareVersion": "...",
      // "source": { "type": "entity-mib" }
    }
  },

  // ── Visual views ─────────────────────────────────────────────────────────
  "views": [
    {
      "viewId": "front",
      "label": "Front Panel",
      "svgFile": "front.svg",            // relative to frontend/public/chassis-assets/<profile>/
      "hotspots": [
        {
          "componentId": "slot-0",       // links hotspot to a component in componentsById
          "x": 42,                       // SVG coordinate (pixels from left)
          "y": 18,                       // SVG coordinate (pixels from top)
          "width": 120,
          "height": 40,
          "tooltip": "Slot 0"
        }
      ]
    }
  ],

  // ── ENTITY-MIB index mapping ──────────────────────────────────────────────
  "physicalIndexToComponentId": {
    "100": "chassis-root",   // entPhysicalIndex → componentId
    "101": "slot-0"
  }
}
```

### Key Fields

| Field | Required | Description |
|-------|----------|-------------|
| `schemaVersion` | ✅ | Must be `"nms.chassisView.v1"` |
| `profileId` | ✅ | Unique string, used for caching and frontend routing |
| `componentsById` | ✅ | Map of all component objects keyed by their `id` |
| `views[].hotspots` | ✅ | Array linking SVG regions to component IDs |
| `physicalIndexToComponentId` | ✅ | Maps ENTITY-MIB `entPhysicalIndex` to component IDs |
| `tree` | ✅ | Hierarchical component tree for the sidebar |

---

## Adding a New Chassis Profile

Follow these steps to add support for a new platform (example: `asr9901`).

### Step 1 — Create the backend data directory

```
backend/app/data/chassis/asr9901/
└── normalized.json
```

Populate `normalized.json` with the schema above. Start from an existing profile (e.g. `asr9006/normalized.json`) as a template.

### Step 2 — Add the SVG artwork

```
frontend/public/chassis-assets/asr9901/
└── front.svg
```

The SVG viewport should match the coordinate system used in `views[].hotspots`. Use `viewBox="0 0 <width> <height>"`.

### Step 3 — Register the profile in `CHASSIS_PROFILE_FILES`

In `backend/app/api/devices.py`:

```python
CHASSIS_PROFILE_FILES = {
    ...
    "asr9901": Path(__file__).resolve().parents[1] / "data" / "chassis" / "asr9901" / "normalized.json",
}
```

### Step 4 — Add the detection rule

In `_chassis_profile_for_device()` (same file):

```python
# Add after existing asr rules:
if "asr" in terms and "9901" in terms:
    return "asr9901"
```

Choose the right position in the evaluation order to avoid false positives against similar model strings.

### Step 5 — Write `physicalIndexToComponentId` mapping

Run an SNMP ENTITY-MIB walk against a real device:

```bash
snmpwalk -v2c -c <community> <ip> ENTITY-MIB::entPhysicalDescr
snmpwalk -v2c -c <community> <ip> ENTITY-MIB::entPhysicalModelName
```

Map the returned `entPhysicalIndex` values to the component IDs you defined in `componentsById`.

### Step 6 — Add tests

In `backend/tests/test_chassis_api.py`, add:

1. A **detection test** — verifies `_chassis_profile_for_device()` returns `"asr9901"` for a device with the expected model string.
2. An **endpoint test** — calls `get_device_chassis()` with a fake session and asserts `profileId`, `schemaVersion`, and hotspot count.

```python
def test_chassis_profile_detects_asr9901_from_device_model():
    device = Device(
        id=uuid.uuid4(), name="asr9901-test",
        ip_address="10.0.0.70", device_type="router",
        model="Cisco ASR 9901", vendor="Cisco",
    )
    assert _chassis_profile_for_device(device, None) == "asr9901"


@pytest.mark.asyncio
async def test_chassis_endpoint_returns_asr9901_profile():
    device_id = uuid.uuid4()
    device = Device(
        id=device_id, name="asr9901-mx01",
        ip_address="10.0.0.71", device_type="router",
        model="Cisco ASR 9901", vendor="Cisco",
    )
    chassis = await get_device_chassis(device_id, _FakeSession(device))
    assert chassis["profileId"] == "Cisco_ASR_9901_Router"
    assert chassis["deviceId"] == str(device_id)
```

Run the test suite: `cd backend && .venv/bin/python3 -m pytest tests/test_chassis_api.py -v`

---

## SNMP Walk → Profile Pipeline

```
Device (SNMP reachable)
        │
        ▼
SNMPEngine.collect_physical_inventory()
  • Walks ENTITY-MIB::entPhysicalTable (OID .1.3.6.1.2.1.47.1.1.1)
  • Returns dict[int, PhysicalInventoryRow]
        │
        ▼
_upsert_physical_inventory_components()
  • Writes/updates rows in physical_inventory_components table
  • Sets metadata_json["source"] = "entity-mib"
        │
        ▼
GET /api/devices/{id}/chassis
  • Loads device + inventory from DB
  • Calls _chassis_profile_for_device() → profile key
  • Loads normalized.json from backend/app/data/chassis/<profile>/
  • Calls _customize_chassis_model():
      ├── Replaces deviceId, deviceName
      ├── Sets source.type = "static-profile" (or "+entity-mib" if data available)
      └── Calls _apply_physical_inventory_to_chassis()
            • Prefers physical_inventory_components table rows (most recent walk)
            • Falls back to inventory.additional_info["physical_inventory"] (JSON blob)
            • Maps entPhysicalIndex → componentId via physicalIndexToComponentId
            • Enriches component with serialNumber, modelName, manufacturer, etc.
        │
        ▼
Frontend receives normalized chassis model
  • Renders SVG from chassis-assets/<profile>/front.svg
  • Overlays interactive hotspots from views[].hotspots
  • Populates sidebar tree from tree[] + componentsById
```

---

## API Contract

### `GET /api/devices/{device_id}/chassis`

Returns a normalized chassis model or 404/422 on error.

**Success response (`200 OK`)**:

```jsonc
{
  "schemaVersion": "nms.chassisView.v1",
  "profileId": "Cisco_NCS55A1",
  "deviceId": "550e8400-e29b-41d4-a716-446655440000",
  "platform": "Cisco NCS 55A1",
  "source": {
    "type": "static-profile+entity-mib",   // or "static-profile"
    "profile": "ncs55a1",
    "deviceName": "core-ncs55a1-mx01",
    "physicalInventory": {
      "available": 48,
      "matched": 44,
      "unmatched": 4
    }
  },
  "tree": [ ... ],
  "componentsById": { ... },
  "views": [ { "viewId": "front", "hotspots": [ ... ] } ],
  "physicalIndexToComponentId": { ... }
}
```

**Error responses**:

| Status | Reason |
|--------|--------|
| `404` | Device not found OR profile `normalized.json` file missing |
| `422` | Profile detection returned `None` (unsupported platform) |
