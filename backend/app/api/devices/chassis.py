"""Chassis-view model building, ENTITY-MIB enrichment, and port detail."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.devices.common import _build_snmp_cred, _get_device_or_404, router
from app.database import get_db
from app.models.alarm import Alarm
from app.models.device import Device
from app.models.interface import Interface
from app.models.inventory import Inventory
from app.models.physical_inventory import PhysicalInventoryComponent
from app.services.snmp.engine import SNMPEngine

# parents[2] == backend/app (this file lives in app/api/devices/)
_CHASSIS_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "chassis"

CHASSIS_PROFILE_FILES = {
    "asr903": _CHASSIS_DATA_DIR / "asr903" / "normalized.json",
    "asr9006": _CHASSIS_DATA_DIR / "asr9006" / "normalized.json",
    "asr920": _CHASSIS_DATA_DIR / "asr920" / "normalized.json",
    # ASR920 12-port variants (real entPhysicalIndex maps from docs/snmpwalks)
    "asr920-12cz": _CHASSIS_DATA_DIR / "asr920-12cz" / "normalized.json",
    "asr920-12sz": _CHASSIS_DATA_DIR / "asr920-12sz" / "normalized.json",
    "asr920-12sz-im": _CHASSIS_DATA_DIR / "asr920-12sz-im" / "normalized.json",
    "ncs55a1": _CHASSIS_DATA_DIR / "ncs55a1" / "normalized.json",
    "ncs55a1-24h": _CHASSIS_DATA_DIR / "ncs55a1-24h" / "normalized.json",
    "ncs55a1-24q6h": _CHASSIS_DATA_DIR / "ncs55a1-24q6h" / "normalized.json",
    "ncs55a1-48q6h": _CHASSIS_DATA_DIR / "ncs55a1-48q6h" / "normalized.json",
    "ncs5501": _CHASSIS_DATA_DIR / "ncs5501" / "normalized.json",
    "ncs5502": _CHASSIS_DATA_DIR / "ncs5502" / "normalized.json",
    "ncs5508": _CHASSIS_DATA_DIR / "ncs5508" / "normalized.json",
    "ncs560": _CHASSIS_DATA_DIR / "ncs560" / "normalized.json",
    # NCS540L_CE sub-model profiles (checked before generic ncs540 fallback)
    "ncs540-16z4": _CHASSIS_DATA_DIR / "ncs540-16z4" / "normalized.json",
    "ncs540-12z16g": _CHASSIS_DATA_DIR / "ncs540-12z16g" / "normalized.json",
    "ncs540-28z4c": _CHASSIS_DATA_DIR / "ncs540-28z4c" / "normalized.json",
    "ncs540-12z20g": _CHASSIS_DATA_DIR / "ncs540-12z20g" / "normalized.json",
    "ncs540-fh-agg": _CHASSIS_DATA_DIR / "ncs540-fh-agg" / "normalized.json",
    "ncs540-fh-csr": _CHASSIS_DATA_DIR / "ncs540-fh-csr" / "normalized.json",
    "ncs540x-4z14g2q": _CHASSIS_DATA_DIR / "ncs540x-4z14g2q" / "normalized.json",
    "ncs540": _CHASSIS_DATA_DIR / "ncs540" / "normalized.json",
    "asr9010": _CHASSIS_DATA_DIR / "asr9010" / "normalized.json",
}


# Exact chassis PID → profile mapping. The PID is entPhysicalModelName on the
# ENTITY-MIB chassis row (entPhysicalClass == chassis(3)); reference walks live
# in docs/snmpwalks/. Exact PIDs are checked before the substring heuristics in
# _chassis_profile_for_device, so a collected device always lands on the right
# profile even when its display model string is generic.
CHASSIS_PID_PROFILES: dict[str, str] = {
    # ASR 900 series (IOS XE)
    "ASR-903": "asr903",
    "ASR-920-4SZ-A": "asr920",
    "ASR-920-4SZ-D": "asr920",
    "ASR-920-8S4Z-PD": "asr920",
    "ASR-920-10SZ-PD": "asr920",
    "ASR-920-12CZ-A": "asr920-12cz",
    "ASR-920-12CZ-D": "asr920-12cz",
    "ASR-920-12SZ-A": "asr920-12sz",
    "ASR-920-12SZ-D": "asr920-12sz",
    "ASR-920-12SZ-IM": "asr920-12sz-im",
    "ASR-920-12SZ-IM-CC": "asr920-12sz-im",
    "ASR-920-20SZ-M": "asr920",
    "ASR-920-24SZ-IM": "asr920",
    "ASR-920-24SZ-M": "asr920",
    "ASR-920-24TZ-M": "asr920",
    "ASR-920U-12SZ-IM": "asr920-12sz-im",
    # ASR 9000 series (IOS XR)
    "ASR-9006": "asr9006",
    "ASR-9006-AC": "asr9006",
    "ASR-9006-DC": "asr9006",
    "ASR-9010": "asr9010",
    "ASR-9010-AC": "asr9010",
    "ASR-9010-DC": "asr9010",
    # NCS 540 (IOS XR)
    "N540-24Z8Q2C-M": "ncs540",
    "N540-24Z8Q2C-SYS": "ncs540",
    "N540-ACC-SYS": "ncs540",
    "N540X-16Z4G8Q2C-A": "ncs540-16z4",
    "N540X-16Z4G8Q2C-D": "ncs540-16z4",
    "N540X-12Z16G-SYS-A": "ncs540-12z16g",
    "N540X-12Z16G-SYS-D": "ncs540-12z16g",
    "N540-28Z4C-SYS-A": "ncs540-28z4c",
    "N540-28Z4C-SYS-D": "ncs540-28z4c",
    "N540-12Z20G-SYS-A": "ncs540-12z20g",
    "N540-12Z20G-SYS-D": "ncs540-12z20g",
    "N540-FH-AGG-SYS": "ncs540-fh-agg",
    "N540-FH-CSR-SYS": "ncs540-fh-csr",
    "N540X-4Z14G2Q-A": "ncs540x-4z14g2q",
    "N540X-4Z14G2Q-D": "ncs540x-4z14g2q",
    # NCS 55xx (IOS XR)
    "NCS-55A1-36H-S": "ncs55a1",
    "NCS-55A1-36H-SE-S": "ncs55a1",
    "NCS-55A1-24H": "ncs55a1-24h",
    "NCS-55A1-24Q6H-S": "ncs55a1-24q6h",
    "NCS-55A1-24Q6H-SS": "ncs55a1-24q6h",
    "NCS-55A1-48Q6H": "ncs55a1-48q6h",
    "NCS-5501": "ncs5501",
    "NCS-5501-SE": "ncs5501",
    "NCS-5502": "ncs5502",
    "NCS-5502-SE": "ncs5502",
    "NCS-5508": "ncs5508",
    # NCS 560 (IOS XR)
    "N560-4-SYS": "ncs560",
    "N560-7-SYS": "ncs560",
    "NCS560-4": "ncs560",
    "NCS560-7": "ncs560",
}

_CHASSIS_CLASS_LABELS = {"3", "chassis"}


def _normalize_pid(value: object) -> str:
    return str(value).strip().rstrip("=").strip().upper()


def _chassis_pid_for_device(
    device: Device,
    inventory: Inventory | None,
    physical_components: list[PhysicalInventoryComponent] | None = None,
) -> str | None:
    """Return the chassis PID for a device, preferring collected ENTITY-MIB data."""
    if physical_components:
        for component in physical_components:
            if component.physical_class == 3 and component.model_name:
                return _normalize_pid(component.model_name)
    for item in _normalize_physical_inventory_items(inventory):
        physical_class = str(item.get("physicalClass", "")).strip().lower()
        model_name = item.get("modelName") or item.get("model")
        if physical_class in _CHASSIS_CLASS_LABELS and model_name:
            return _normalize_pid(model_name)
    # Fall back to model strings that are themselves exact PIDs.
    for candidate in ((inventory.hardware_model if inventory else None), device.model):
        if candidate and _normalize_pid(candidate) in CHASSIS_PID_PROFILES:
            return _normalize_pid(candidate)
    return None


def _device_inventory_terms(device: Device, inventory: Inventory | None) -> str:
    values: list[str] = [
        device.name,
        device.device_type,
        device.model or "",
        device.platform_family or "",
        device.vendor or "",
    ]
    if inventory:
        values.extend([inventory.hardware_model or "", inventory.serial_number or ""])
        info = inventory.additional_info or {}
        for key in ("model", "platform", "platformId", "device_type", "product_name", "chassis_model"):
            value = info.get(key)
            if value:
                values.append(str(value))
    return " ".join(values).lower().replace("-", " ").replace("_", " ")


def _chassis_profile_for_device(
    device: Device,
    inventory: Inventory | None,
    physical_components: list[PhysicalInventoryComponent] | None = None,
) -> str | None:
    pid = _chassis_pid_for_device(device, inventory, physical_components)
    if pid is not None:
        profile = CHASSIS_PID_PROFILES.get(pid)
        if profile is not None:
            return profile
    terms = _device_inventory_terms(device, inventory)
    compact_terms = terms.replace(" ", "")
    # NCS5500 fixed-port routers (check before generic ncs55a1 catch-all)
    if "ncs5508" in compact_terms:
        return "ncs5508"
    if "ncs5516" in compact_terms:
        return "ncs5516"
    if "ncs5502" in compact_terms:
        return "ncs5502"
    if "ncs5501" in compact_terms:
        return "ncs5501"
    # NCS55A1 sub-variants (check specific models before generic fallback)
    if "ncs55a1" in compact_terms:
        if "48q6h" in compact_terms:
            return "ncs55a1-48q6h"
        if "24q6h" in compact_terms:
            return "ncs55a1-24q6h"
        if "24h" in compact_terms:
            return "ncs55a1-24h"
        return "ncs55a1"
    if "ncs560" in compact_terms:
        return "ncs560"
    # NCS540L_CE sub-models: check specific variants before the generic ncs540 fallback.
    # Use compact_terms (spaces/dashes/underscores removed, lowercased) for matching.
    #
    # N540X-16Z4G8Q2C-D/A  → "n540x16z4g8q2cd" / "...a"   (540x + 16z4)
    # N540X-12Z16G-SYS-D/A → "ncs540x12z16gsysd" / "...a" (540x + 12z16g)
    # N540-28Z4C-SYS-D/A   → "n54028z4csysd" / "...a"     (n540 + 28z4c, no 540x)
    # N540-12Z20G-SYS-D/A  → "n54012z20gsysd" / "...a"    (n540 + 12z20g)
    # N540-FH-AGG-SYS      → "n540fhaggsys"              (n540 + fhagg)
    # N540-FH-CSR-SYS      → "n540fhcsrsys"              (n540 + fhcsr)
    # N540X-4Z14G2Q-D/A    → "n540x4z14g2qd" / "...a"    (540x + 4z14g2q)
    if "16z4" in compact_terms and "540x" in compact_terms:
        return "ncs540-16z4"
    if "12z16g" in compact_terms and "540x" in compact_terms:
        return "ncs540-12z16g"
    if "28z4c" in compact_terms and "n540" in compact_terms:
        return "ncs540-28z4c"
    if "12z20g" in compact_terms and "n540" in compact_terms:
        return "ncs540-12z20g"
    if "fhagg" in compact_terms and "n540" in compact_terms:
        return "ncs540-fh-agg"
    if "fhcsr" in compact_terms and "n540" in compact_terms:
        return "ncs540-fh-csr"
    if "4z14g2q" in compact_terms and "540x" in compact_terms:
        return "ncs540x-4z14g2q"
    if "ncs540" in compact_terms or "n540" in compact_terms:
        return "ncs540"
    if "asr" in terms and "920" in terms:
        # 12-port variants get dedicated profiles; check before the generic fallback.
        if "12cz" in compact_terms:
            return "asr920-12cz"
        if "12szim" in compact_terms:
            return "asr920-12sz-im"
        if "12sz" in compact_terms:
            return "asr920-12sz"
        return "asr920"
    if "asr" in terms and "903" in terms:
        return "asr903"
    if "asr" in terms and "9006" in terms:
        return "asr9006"
    if "asr" in terms and "9010" in terms:
        return "asr9010"
    return None


def _load_chassis_profile(profile: str) -> dict[str, Any]:
    path = CHASSIS_PROFILE_FILES.get(profile)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Chassis profile is not available")
    return json.loads(path.read_text(encoding="utf-8"))


def _first_live_inventory_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_physical_inventory_items(inventory: Inventory | None) -> list[dict[str, Any]]:
    if inventory is None or not inventory.additional_info:
        return []

    info = inventory.additional_info
    raw = (
        info.get("physical_inventory")
        or info.get("physicalInventory")
        or info.get("entity_mib")
        or info.get("entityMib")
        or []
    )
    if isinstance(raw, dict):
        raw_items: list[Any] = list(raw.values())
    elif isinstance(raw, list):
        raw_items = raw
    else:
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        physical_index = _first_live_inventory_value(
            item,
            "physicalIndex",
            "physical_index",
            "entPhysicalIndex",
            "index",
        )
        if physical_index is None:
            continue
        normalized.append({**item, "physicalIndex": str(physical_index)})
    return normalized


def _physical_component_to_chassis_item(component: PhysicalInventoryComponent) -> dict[str, Any]:
    return {
        "physicalIndex": str(component.physical_index),
        "description": component.description,
        "vendorType": component.vendor_type,
        "containedPhysicalIndex": component.contained_physical_index,
        "physicalClass": component.physical_class,
        "parentRelPos": component.parent_rel_pos,
        "name": component.name,
        "hardwareVersion": component.hardware_version,
        "firmwareVersion": component.firmware_version,
        "softwareVersion": component.software_version,
        "serialNumber": component.serial_number,
        "manufacturer": component.manufacturer,
        "modelName": component.model_name,
        "alias": component.alias,
        "assetId": component.asset_id,
        "isFRUable": component.is_fru,
    }


def _physical_components_to_chassis_items(
    components: list[PhysicalInventoryComponent] | None,
) -> list[dict[str, Any]]:
    if not components:
        return []
    return [_physical_component_to_chassis_item(component) for component in components]


def _apply_physical_inventory_to_chassis(
    chassis: dict[str, Any],
    inventory: Inventory | None,
    physical_components: list[PhysicalInventoryComponent] | None = None,
) -> dict[str, int]:
    physical_inventory = _physical_components_to_chassis_items(physical_components)
    if not physical_inventory:
        physical_inventory = _normalize_physical_inventory_items(inventory)
    if not physical_inventory:
        return {"available": 0, "matched": 0, "unmatched": 0}

    live_by_index = {str(item["physicalIndex"]): item for item in physical_inventory}
    physical_index_map = chassis.get("physicalIndexToComponentId") or {}
    components = chassis.get("componentsById") or {}
    matched = 0

    for physical_index, component_id in physical_index_map.items():
        live_item = live_by_index.get(str(physical_index))
        component = components.get(component_id)
        if not live_item or not isinstance(component, dict):
            continue

        display_name = _first_live_inventory_value(live_item, "name", "displayName", "description")
        description = _first_live_inventory_value(live_item, "description", "descr")
        model_name = _first_live_inventory_value(live_item, "modelName", "model", "typeId", "pid")
        serial_number = _first_live_inventory_value(live_item, "serialNumber", "serial_number", "serial")
        manufacturer = _first_live_inventory_value(live_item, "manufacturer", "mfgName", "vendor")
        hardware_version = _first_live_inventory_value(live_item, "hardwareVersion", "hardware_rev", "hwRev")
        contained_in = _first_live_inventory_value(
            live_item,
            "containedPhysicalIndex",
            "contained_in",
            "entPhysicalContainedIn",
        )

        if display_name:
            component["name"] = str(display_name)
            component["displayName"] = str(display_name)
        if description:
            component["description"] = str(description)
        if model_name:
            component["typeId"] = str(model_name)
        if serial_number:
            component["serialNumber"] = str(serial_number)
        if manufacturer:
            component["manufacturer"] = str(manufacturer)
        if hardware_version:
            component["hardwareVersion"] = str(hardware_version)
        if contained_in is not None:
            component["containedPhysicalIndex"] = contained_in
        if "isFRUable" in live_item:
            component["isFRUable"] = bool(live_item["isFRUable"])

        component["source"] = {
            **(component.get("source") or {}),
            "type": "entity-mib",
            "physicalIndex": physical_index,
        }
        matched += 1

    return {
        "available": len(physical_inventory),
        "matched": matched,
        "unmatched": max(len(physical_inventory) - matched, 0),
    }


def _customize_chassis_model(
    model: dict[str, Any],
    device: Device,
    inventory: Inventory | None,
    profile: str,
    physical_components: list[PhysicalInventoryComponent] | None = None,
) -> dict[str, Any]:
    chassis = copy.deepcopy(model)
    chassis["deviceId"] = str(device.id)
    if inventory and inventory.hardware_model:
        chassis["platform"] = inventory.hardware_model
    elif device.model:
        chassis["platform"] = device.model

    live_inventory = _apply_physical_inventory_to_chassis(chassis, inventory, physical_components)
    source_type = "static-profile"
    if live_inventory["matched"]:
        source_type = "static-profile+entity-mib"

    chassis["source"] = {
        **(chassis.get("source") or {}),
        "type": source_type,
        "profile": profile,
        "deviceId": str(device.id),
        "deviceName": device.name,
        "physicalInventory": live_inventory,
    }

    root = chassis.get("tree", [{}])[0]
    component_id = root.get("componentId")
    if component_id and component_id in chassis.get("componentsById", {}):
        component = chassis["componentsById"][component_id]
        component["name"] = device.name
        component["displayName"] = device.name
        root["label"] = device.name

    return chassis


def _physical_row_payload(row: Any, collected_at: datetime) -> dict[str, Any]:
    return {
        "description": row.description,
        "vendor_type": row.vendor_type,
        "contained_physical_index": row.contained_in,
        "physical_class": row.physical_class,
        "parent_rel_pos": row.parent_rel_pos,
        "name": row.name,
        "hardware_version": row.hardware_rev,
        "firmware_version": row.firmware_rev,
        "software_version": row.software_rev,
        "serial_number": row.serial_number,
        "manufacturer": row.manufacturer,
        "model_name": row.model_name,
        "alias": row.alias,
        "asset_id": row.asset_id,
        "is_fru": row.is_fru,
        "metadata_json": {
            "vendorType": row.vendor_type,
            "source": "entity-mib",
        },
        "collected_at": collected_at,
    }


async def _upsert_physical_inventory_components(
    db: AsyncSession,
    device_id: uuid.UUID,
    rows: dict[int, Any],
    collected_at: datetime,
) -> list[PhysicalInventoryComponent]:
    result = await db.execute(
        select(PhysicalInventoryComponent).where(PhysicalInventoryComponent.device_id == device_id)
    )
    existing = {component.physical_index: component for component in result.scalars().all()}
    touched: list[PhysicalInventoryComponent] = []

    for physical_index, row in rows.items():
        component = existing.get(physical_index)
        if component is None:
            component = PhysicalInventoryComponent(device_id=device_id, physical_index=physical_index)
            db.add(component)
        for key, value in _physical_row_payload(row, collected_at).items():
            setattr(component, key, value)
        touched.append(component)

    return sorted(touched, key=lambda item: item.physical_index)


@router.post("/{id}/chassis/collect")
async def collect_device_chassis_inventory(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Collect ENTITY-MIB physical inventory and persist it for chassis-view enrichment."""
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    snmp = SNMPEngine()
    rows = await snmp.get_physical_inventory(device.ip_address, snmp_cred)
    collected_at = datetime.now()

    result = await db.execute(select(Inventory).where(Inventory.device_id == id))
    inventory = result.scalar_one_or_none()
    if inventory is None:
        inventory = Inventory(device_id=id)
        db.add(inventory)

    physical_components = await _upsert_physical_inventory_components(db, id, rows, collected_at)

    additional_info = dict(inventory.additional_info or {})
    physical_inventory = [row.to_chassis_inventory() for row in sorted(rows.values(), key=lambda item: item.physical_index)]
    additional_info["physical_inventory"] = physical_inventory
    additional_info["physical_inventory_source"] = "entity-mib"
    additional_info["physical_inventory_collected_at"] = collected_at.isoformat()
    inventory.additional_info = additional_info
    await db.flush()

    return {
        "deviceId": str(id),
        "source": "entity-mib",
        "components": len(physical_inventory),
        "tableComponents": len(physical_components),
        "persisted": True,
    }


@router.get("/{id}/chassis")
async def get_device_chassis(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return a normalized chassis-view model for a supported device."""
    result = await db.execute(
        select(Device)
        .options(selectinload(Device.inventory))
        .where(Device.id == id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    physical_result = await db.execute(
        select(PhysicalInventoryComponent)
        .where(PhysicalInventoryComponent.device_id == id)
        .order_by(PhysicalInventoryComponent.physical_index.asc())
    )
    physical_components = list(physical_result.scalars().all())

    profile = _chassis_profile_for_device(device, device.inventory, physical_components)
    if profile is None:
        raise HTTPException(status_code=404, detail="No chassis profile is available for this device")
    chassis_model = _customize_chassis_model(
        _load_chassis_profile(profile),
        device,
        device.inventory,
        profile,
        physical_components,
    )

    # ── Alarm overlay ────────────────────────────────────────────────────────
    alarm_result = await db.execute(
        select(Alarm)
        .where(Alarm.device_id == id, Alarm.state == "active")
    )
    active_alarms = list(alarm_result.scalars().all())

    severity_rank: dict[str, int] = {
        "critical": 5,
        "major": 4,
        "minor": 3,
        "warning": 2,
        "info": 1,
    }

    alarms_by_component: dict[str, dict] = {}
    alarm_summary: dict[str, int] = {"critical": 0, "major": 0, "minor": 0, "warning": 0, "total": 0}
    phys_idx_map: dict[str, str] = chassis_model.get("physicalIndexToComponentId", {})

    for alarm in active_alarms:
        sev = (alarm.severity or "info").lower()
        # count toward summary regardless of component match
        if sev in alarm_summary:
            alarm_summary[sev] = alarm_summary[sev] + 1
        alarm_summary["total"] = alarm_summary["total"] + 1

        obj_id = alarm.object_id or ""
        component_id: str | None = None

        # Try matching by physicalIndex stored in object_id
        if obj_id and obj_id in phys_idx_map:
            component_id = phys_idx_map[obj_id]

        # Fallback: scan componentsById for a name/displayName match
        if component_id is None and obj_id:
            obj_id_lower = obj_id.lower()
            for cid, comp in chassis_model.get("componentsById", {}).items():
                comp_name = (comp.get("name") or "").lower()
                comp_display = (comp.get("displayName") or "").lower()
                if obj_id_lower in (comp_name, comp_display):
                    component_id = cid
                    break

        if component_id is None:
            continue

        entry = alarms_by_component.setdefault(component_id, {"maxSeverity": "info", "count": 0})
        entry["count"] += 1
        if severity_rank.get(sev, 0) > severity_rank.get(entry["maxSeverity"], 0):
            entry["maxSeverity"] = sev

    chassis_model["alarmsByComponentId"] = alarms_by_component
    chassis_model["alarmSummary"] = alarm_summary
    return chassis_model


@router.get("/{id}/chassis/ports/{physical_index}")
async def get_chassis_port_detail(
    id: uuid.UUID,
    physical_index: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return component, interface, and active alarm data for a chassis port."""
    # Called for its side-effect: raises HTTP 404 when the device id is unknown.
    _ = await _get_device_or_404(db, id)

    # 1. Look up the physical inventory component
    comp_result = await db.execute(
        select(PhysicalInventoryComponent).where(
            PhysicalInventoryComponent.device_id == id,
            PhysicalInventoryComponent.physical_index == physical_index,
        )
    )
    component = comp_result.scalar_one_or_none()
    if component is None:
        raise HTTPException(status_code=404, detail="Physical inventory component not found")

    # 2. Find matching Interface — try by if_index from metadata, then by name match
    iface_result = await db.execute(
        select(Interface).where(
            Interface.device_id == id,
            or_(
                Interface.name == component.name,
                Interface.alias == component.name,
                Interface.description == component.name,
            ),
        ).limit(1)
    )
    interface = iface_result.scalar_one_or_none()

    # 3. Active alarms for this device, limited to 10 ordered by severity then last_seen
    severity_rank = case(
        {"critical": 0, "major": 1, "minor": 2, "warning": 3, "info": 4},
        value=Alarm.severity,
        else_=5,
    )
    alarms_result = await db.execute(
        select(Alarm)
        .where(
            Alarm.device_id == id,
            Alarm.state == "active",
        )
        .order_by(severity_rank.asc(), Alarm.last_seen.desc())
        .limit(10)
    )
    alarms = alarms_result.scalars().all()

    # Build response
    component_data: dict[str, Any] = {
        "physicalIndex": component.physical_index,
        "name": component.name,
        "description": component.description,
        "modelName": component.model_name,
        "serialNumber": component.serial_number,
        "hardwareVersion": component.hardware_version,
        "firmwareVersion": component.firmware_version,
        "softwareVersion": component.software_version,
        "manufacturer": component.manufacturer,
        "alias": component.alias,
        "isFru": component.is_fru,
        "physicalClass": component.physical_class,
    }

    interface_data: dict[str, Any] | None = None
    if interface is not None:
        interface_data = {
            "id": str(interface.id),
            "name": interface.name,
            "alias": interface.alias,
            "adminStatus": interface.admin_status,
            "operStatus": interface.oper_status,
            "speedBps": interface.speed_bps,
            "description": interface.description,
            "macAddress": interface.mac_address,
            "role": interface.role,
        }
        # Counters may be stored in metadata_json
        meta = interface.metadata_json or {}
        interface_data["inOctets"] = meta.get("in_octets")
        interface_data["outOctets"] = meta.get("out_octets")
        interface_data["inErrors"] = meta.get("in_errors")
        interface_data["outErrors"] = meta.get("out_errors")

    alarms_data = [
        {
            "id": str(alarm.id),
            "severity": alarm.severity,
            "category": alarm.category,
            "eventType": alarm.event_type,
            "message": alarm.message,
            "state": alarm.state,
            "lastSeen": alarm.last_seen.isoformat() if alarm.last_seen else None,
            "firstSeen": alarm.first_seen.isoformat() if alarm.first_seen else None,
            "occurrenceCount": alarm.occurrence_count,
            "ackBy": alarm.ack_by,
        }
        for alarm in alarms
    ]

    return {
        "deviceId": str(id),
        "physicalIndex": physical_index,
        "component": component_data,
        "interface": interface_data,
        "alarms": alarms_data,
    }
