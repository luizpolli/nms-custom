"""Device API routes."""

from __future__ import annotations

import copy
import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import async_session_factory, get_db
from app.models.alarm import Alarm
from app.models.credential import Credential
from app.models.device import Device
from app.models.interface import Interface
from app.models.inventory import Inventory
from app.models.physical_inventory import PhysicalInventoryComponent
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.schemas.interface import InterfaceRead as ManagedInterfaceRead
from app.security.auth import PERM_COMMANDS_EXPORT, Principal, require_command_permission
from app.security.crypto import CredentialVault
from app.services.kpi.engine import KPIEngine
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential, SNMPPoller

router = APIRouter()
settings = Settings()

CHASSIS_PROFILE_FILES = {
    "asr903": Path(__file__).resolve().parents[1] / "data" / "chassis" / "asr903" / "normalized.json",
    "asr9006": Path(__file__).resolve().parents[1] / "data" / "chassis" / "asr9006" / "normalized.json",
    "asr920": Path(__file__).resolve().parents[1] / "data" / "chassis" / "asr920" / "normalized.json",
    "ncs55a1": Path(__file__).resolve().parents[1] / "data" / "chassis" / "ncs55a1" / "normalized.json",
    "ncs560": Path(__file__).resolve().parents[1] / "data" / "chassis" / "ncs560" / "normalized.json",
    "ncs540": Path(__file__).resolve().parents[1] / "data" / "chassis" / "ncs540" / "normalized.json",
    "asr9010": Path(__file__).resolve().parents[1] / "data" / "chassis" / "asr9010" / "normalized.json",
}


async def _get_device_or_404(db: AsyncSession, device_id: uuid.UUID) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _build_snmp_cred(device: Device) -> SNMPCredential:
    if not device.credential:
        raise HTTPException(status_code=422, detail="Device has no credential attached")
    cred = device.credential
    vault = CredentialVault.from_settings(settings)
    plain = vault.decrypt(cred.auth_key, cred.id.bytes)
    return SNMPCredential(
        version=cred.snmp_version,
        community=plain,
        user=cred.username,
        auth_protocol="SHA" if cred.snmp_version == "v3" and plain else None,
        auth_key=plain if cred.snmp_version == "v3" else None,
        priv_protocol="AES128" if cred.snmp_version == "v3" and cred.enc_key else None,
        priv_key=vault.decrypt(cred.enc_key, cred.id.bytes) if cred.enc_key else None,
        port=cred.port,
    )


class InterfaceRead(BaseModel):
    if_index: int
    descr: str | None = None
    type: int | None = None
    speed: int | None = None
    admin_status: int | None = None
    oper_status: int | None = None
    in_octets: int | None = None
    out_octets: int | None = None
    in_errors: int | None = None
    out_errors: int | None = None
    alias: str | None = None
    phys_address: str | None = None


EPNM_EXPORT_COLUMNS = [
    "Reachability",
    "Admin Status",
    "Device Name",
    "IP Address",
    "Device Type",
    "Last Inventory Collection Status",
    "Last Successful Collection Time",
    "Software Version",
    "Creation Timestamp",
    "Vendor",
]

EPNM_CREDENTIAL_EXPORT_COLUMNS = [
    "CLI Username",
    "CLI Password",
    "SNMP Version",
    "SNMP Community",
    "SNMP Write Community",
    "SNMPv3 Username",
    "SNMPv3 Auth Type",
    "SNMPv3 Auth Password",
    "SNMPv3 Privacy Type",
    "SNMPv3 Privacy Password",
    "Credential Profile",
]


class DeviceExportRow(BaseModel):
    reachability: str = ""
    admin_status: str = ""
    device_name: str = ""
    ip_address: str = ""
    device_type: str = ""
    last_inventory_collection_status: str = ""
    last_successful_collection_time: str = ""
    software_version: str = ""
    creation_timestamp: str = ""
    vendor: str = ""


class DeviceCredentialExportRow(BaseModel):
    cli_username: str = ""
    cli_password: str = ""
    snmp_version: str = ""
    snmp_community: str = ""
    snmp_write_community: str = ""
    snmpv3_username: str = ""
    snmpv3_auth_type: str = ""
    snmpv3_auth_password: str = ""
    snmpv3_privacy_type: str = ""
    snmpv3_privacy_password: str = ""
    credential_profile: str = ""


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _inventory_value(inventory: Inventory | None, *keys: str) -> str:
    if inventory is None:
        return ""
    for key in keys:
        value = getattr(inventory, key, None)
        if value:
            return _csv_value(value)
    info = inventory.additional_info or {}
    for key in keys:
        value = info.get(key)
        if value:
            return _csv_value(value)
    return ""


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


def _chassis_profile_for_device(device: Device, inventory: Inventory | None) -> str | None:
    terms = _device_inventory_terms(device, inventory)
    compact_terms = terms.replace(" ", "")
    if "ncs55a1" in compact_terms:
        return "ncs55a1"
    if "ncs560" in compact_terms:
        return "ncs560"
    if "ncs540" in compact_terms or "n540" in compact_terms:
        return "ncs540"
    if "asr" in terms and "920" in terms:
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
        raw_items = raw.values()
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


def _decrypt_or_blank(vault: CredentialVault, ciphertext: str | None, record_id: bytes) -> str:
    if not ciphertext:
        return ""
    return vault.decrypt(ciphertext, record_id)


def _device_export_row(device: Device) -> DeviceExportRow:
    inventory = device.inventory
    return DeviceExportRow(
        reachability=device.status,
        admin_status=device.lifecycle_state,
        device_name=device.name,
        ip_address=device.ip_address,
        device_type=device.device_type,
        last_inventory_collection_status=_inventory_value(inventory, "collection_status", "status"),
        last_successful_collection_time=_inventory_value(inventory, "last_successful_collection_time", "updated_at"),
        software_version=_inventory_value(inventory, "software_version", "firmware_version") or _csv_value(device.software_version) or _csv_value(device.os_type),
        creation_timestamp=_csv_value(device.created_at),
        vendor=_csv_value(device.vendor),
    )


def _credential_export_row(credential: Credential | None, vault: CredentialVault | None) -> DeviceCredentialExportRow:
    if credential is None or vault is None:
        return DeviceCredentialExportRow()
    auth_secret = _decrypt_or_blank(vault, credential.auth_key, credential.id.bytes)
    privacy_secret = _decrypt_or_blank(vault, credential.enc_key, credential.id.bytes)
    is_v3 = credential.snmp_version.lower() == "v3"
    is_snmp = credential.protocol.lower() == "snmp"
    return DeviceCredentialExportRow(
        cli_username=credential.username if not is_snmp else "",
        cli_password=auth_secret if not is_snmp else "",
        snmp_version=credential.snmp_version,
        snmp_community=auth_secret if is_snmp and not is_v3 else "",
        snmpv3_username=credential.username if is_v3 else "",
        snmpv3_auth_type="SHA" if is_v3 and auth_secret else "",
        snmpv3_auth_password=auth_secret if is_v3 else "",
        snmpv3_privacy_type="AES128" if is_v3 and privacy_secret else "",
        snmpv3_privacy_password=privacy_secret if is_v3 else "",
        credential_profile=credential.name,
    )


@router.get("/export")
async def export_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_command_permission(PERM_COMMANDS_EXPORT))],
    export_format: str = Query("csv", alias="format", pattern="^csv$"),
    include_credentials: bool = Query(False),
) -> Response:
    """Export devices using Cisco EPNM-style CSV columns."""
    del export_format
    if include_credentials and principal.role.lower() not in {"root", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="root/admin role required to export device credentials",
        )

    result = await db.execute(
        select(Device)
        .options(selectinload(Device.credential), selectinload(Device.inventory))
        .order_by(Device.name)
    )
    devices = result.scalars().all()
    headers = EPNM_EXPORT_COLUMNS + (EPNM_CREDENTIAL_EXPORT_COLUMNS if include_credentials else [])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()

    vault = CredentialVault.from_settings(settings) if include_credentials else None
    for device in devices:
        base = _device_export_row(device)
        row = {
            "Reachability": base.reachability,
            "Admin Status": base.admin_status,
            "Device Name": base.device_name,
            "IP Address": base.ip_address,
            "Device Type": base.device_type,
            "Last Inventory Collection Status": base.last_inventory_collection_status,
            "Last Successful Collection Time": base.last_successful_collection_time,
            "Software Version": base.software_version,
            "Creation Timestamp": base.creation_timestamp,
            "Vendor": base.vendor,
        }
        if include_credentials:
            cred = _credential_export_row(device.credential, vault)
            row.update(
                {
                    "CLI Username": cred.cli_username,
                    "CLI Password": cred.cli_password,
                    "SNMP Version": cred.snmp_version,
                    "SNMP Community": cred.snmp_community,
                    "SNMP Write Community": cred.snmp_write_community,
                    "SNMPv3 Username": cred.snmpv3_username,
                    "SNMPv3 Auth Type": cred.snmpv3_auth_type,
                    "SNMPv3 Auth Password": cred.snmpv3_auth_password,
                    "SNMPv3 Privacy Type": cred.snmpv3_privacy_type,
                    "SNMPv3 Privacy Password": cred.snmpv3_privacy_password,
                    "Credential Profile": cred.credential_profile,
                }
            )
        writer.writerow(row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="devices_export.csv"'},
    )


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    status: str | None = None,
    vendor: str | None = None,
    tag: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[DeviceRead]:
    stmt = select(Device)
    if q:
        stmt = stmt.where(Device.name.ilike(f"%{q}%") | Device.ip_address.ilike(f"%{q}%"))
    if status:
        stmt = stmt.where(Device.status == status)
    if vendor:
        stmt = stmt.where(Device.vendor == vendor)
    if tag:
        stmt = stmt.where(Device.tags.any(tag))
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    devices = result.scalars().all()
    return [DeviceRead.model_validate(d) for d in devices]


@router.post("", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = Device(**body.model_dump())
    db.add(device)
    await db.flush()
    await db.refresh(device)
    return DeviceRead.model_validate(device)


class BulkDeviceRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(None, max_length=255, validation_alias=AliasChoices("name", "device_name"))
    host: str | None = Field(None, max_length=45, validation_alias=AliasChoices("host", "ip_address"))
    vendor: str = Field("cisco", max_length=100)
    user: str | None = Field(None, max_length=255, validation_alias=AliasChoices("user", "cli_username"))
    password: str | None = Field(None, validation_alias=AliasChoices("password", "cli_password", "snmp_community"))
    model: str | None = Field(None, max_length=255)
    site: str | None = Field(None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    device_type: str | None = Field(None, max_length=50)
    # Field name kept in camelCase to match EPNM CSV export columns.
    licenceLevel: str | None = Field(None, validation_alias=AliasChoices("licenceLevel", "licencelevel", "licence_level"))  # noqa: N815
    snmp_version: str | None = Field(None, max_length=5)
    snmp_community: str | None = None
    snmp_write_community: str | None = None
    snmp_retries: int | None = None
    snmp_timeout: int | None = None
    snmp_port: int | None = Field(None, ge=1, le=65535)
    protocol: str | None = Field(None, max_length=10)
    cli_port: int | None = Field(None, ge=1, le=65535)
    cli_username: str | None = None
    cli_password: str | None = None
    cli_enable_password: str | None = None
    cli_timeout: int | None = None
    snmpv3_user_name: str | None = Field(None, validation_alias=AliasChoices("snmpv3_user_name", "snmpv3_username"))
    snmpv3_auth_type: str | None = None
    snmpv3_auth_password: str | None = None
    snmpv3_privacy_type: str | None = None
    snmpv3_privacy_password: str | None = None
    http_server: str | None = None
    http_port: int | None = Field(None, ge=1, le=65535)
    http_config_username: str | None = None
    http_config_password: str | None = None
    http_monitor_username: str | None = None
    http_monitor_password: str | None = None
    credential_profile: str | None = Field(None, max_length=255)
    location_groupname: str | None = Field(None, max_length=255)
    user_groupname: str | None = None
    region: str | None = None
    country: str | None = None
    state: str | None = None
    city: str | None = None
    county: str | None = None
    street: str | None = None
    building: str | None = None
    floor: str | None = None
    room: str | None = None
    longitude: str | None = None
    latitude: str | None = None
    altitude: str | None = None
    assigned_network_role: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_required_identity(self) -> BulkDeviceRow:
        if not self.name:
            raise ValueError("name or device_name is required")
        if not self.host:
            raise ValueError("host or ip_address is required")
        if not self.password and not self.snmp_community and not self.snmpv3_auth_password:
            raise ValueError("password, snmp_community, or snmpv3_auth_password is required")
        return self


def _first_present(*values: str | None) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _row_location(row: BulkDeviceRow) -> str | None:
    return _first_present(row.site, row.location_groupname, row.room, row.floor, row.building, row.street, row.city, row.state, row.country, row.region)


def _row_site(row: BulkDeviceRow) -> str | None:
    return _first_present(row.location_groupname, row.site, row.city, row.region)


def _row_snmp_version(row: BulkDeviceRow) -> str:
    version = (row.snmp_version or "").lower().replace("snmp", "").strip()
    if row.snmpv3_user_name or row.snmpv3_auth_password or version == "3":
        return "v3"
    if version in {"1", "v1"}:
        return "v1"
    return "v2c"


def _row_secret(row: BulkDeviceRow, version: str) -> str:
    if version == "v3":
        return _first_present(row.snmpv3_auth_password, row.password, row.cli_password) or ""
    return _first_present(row.snmp_community, row.password) or ""


class BulkImportRequest(BaseModel):
    rows: list[BulkDeviceRow]


class BulkImportFailure(BaseModel):
    row: int
    name: str
    error: str


class BulkImportResponse(BaseModel):
    created: int
    failed: list[BulkImportFailure]


@router.post("/bulk", response_model=BulkImportResponse, status_code=status.HTTP_201_CREATED)
async def bulk_import_devices(
    body: BulkImportRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkImportResponse:
    """Import devices from a parsed CSV payload.

    Each row creates a Credential (SNMP v2c) and a Device linked to it.
    Failures are isolated per-row; successful rows commit even if others fail.
    """
    vault = CredentialVault.from_settings(settings)
    created = 0
    failed: list[BulkImportFailure] = []

    for idx, row in enumerate(body.rows):
        sp = await db.begin_nested()
        try:
            host = row.host or ""
            name = row.name or host
            snmp_version = _row_snmp_version(row)
            secret = _row_secret(row, snmp_version)
            username = _first_present(row.snmpv3_user_name, row.user, row.cli_username) or ""
            existing = await db.execute(select(Device).where(Device.ip_address == host))
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"device with IP {host} already exists")

            cred = Credential(
                name=row.credential_profile or f"{name}-cred",
                hostname=host,
                username=username,
                auth_key="",
                protocol=row.protocol or "snmp",
                snmp_version=snmp_version,
                port=row.snmp_port or 161,
            )
            db.add(cred)
            await db.flush()
            cred.auth_key = vault.encrypt(secret, cred.id.bytes)
            if snmp_version == "v3" and row.snmpv3_privacy_password:
                cred.enc_key = vault.encrypt(row.snmpv3_privacy_password, cred.id.bytes)

            device = Device(
                name=name,
                ip_address=host,
                device_type=row.device_type or "router",
                vendor=row.vendor,
                model=row.model,
                location=_row_location(row),
                site_id=_row_site(row),
                role=row.assigned_network_role,
                tags=row.tags,
                credential_id=cred.id,
            )
            db.add(device)
            await db.flush()
            await sp.commit()
            created += 1
        except Exception as exc:
            await sp.rollback()
            logger.warning("bulk import row {} failed: {}", idx, exc)
            failed.append(BulkImportFailure(row=idx, name=row.name or row.host or "", error=str(exc)))

    return BulkImportResponse(created=created, failed=failed)


class VerifyCredentialsRequest(BaseModel):
    """Loose payload — only the SNMP block is required to attempt reachability."""

    ip_address: str | None = None
    dns_name: str | None = None
    identification: str | None = None
    snmp: dict | None = None
    telnet_ssh: dict | None = None
    http: dict | None = None


class VerifyCredentialsResponse(BaseModel):
    ok: bool
    sys_descr: str | None = None
    error: str | None = None


def _snmp_priv_protocol(value: object) -> str | None:
    """Normalize UI labels to SNMPPoller protocol names."""
    if not value:
        return None
    raw = str(value).upper()
    if "DES" in raw:
        return "DES"
    if "256" in raw:
        return "AES256"
    if "196" in raw or "192" in raw:
        return "AES192"
    if "128" in raw or "AES" in raw:
        return "AES128"
    return raw


@router.post("/verify-credentials", response_model=VerifyCredentialsResponse)
async def verify_credentials(body: VerifyCredentialsRequest) -> VerifyCredentialsResponse:
    """Quick reachability check using SNMP sysDescr (1.3.6.1.2.1.1.1.0).

    Best-effort: tries SNMP first using whatever was provided in the form. Does
    not persist anything. Used by the Add Device dialog's "Verify Credentials".
    """
    target = (
        body.ip_address
        if (body.identification or "ip") == "ip"
        else body.dns_name
    ) or body.ip_address or body.dns_name
    if not target:
        return VerifyCredentialsResponse(ok=False, error="No IP/DNS provided")

    snmp = body.snmp or {}
    version = snmp.get("version", "v2c")
    cred = SNMPCredential(
        version=version,
        community=snmp.get("read_community") or "public",
        user=snmp.get("v3_username"),
        auth_protocol=(snmp.get("v3_auth_type") or "").replace("HMAC-", "") or None,
        auth_key=snmp.get("v3_auth_password"),
        priv_protocol=_snmp_priv_protocol(snmp.get("v3_priv_type")),
        priv_key=snmp.get("v3_priv_password"),
        port=int(snmp.get("port") or 161),
        timeout=float(snmp.get("timeout") or 5),
        retries=int(snmp.get("retries") or 1),
    )

    try:
        poller = SNMPPoller()
    except RuntimeError as exc:
        return VerifyCredentialsResponse(ok=False, error=str(exc))

    result = await poller.get(target, ["1.3.6.1.2.1.1.1.0"], cred)
    if result.success and result.varbinds:
        sys_descr = next(iter(result.varbinds.values()), None)
        return VerifyCredentialsResponse(ok=True, sys_descr=sys_descr)
    return VerifyCredentialsResponse(ok=False, error=result.error or "No response")


@router.get("/{id}", response_model=DeviceRead)
async def get_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = await _get_device_or_404(db, id)
    return DeviceRead.model_validate(device)


@router.patch("/{id}", response_model=DeviceRead)
async def update_device(
    id: uuid.UUID,
    body: DeviceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceRead:
    device = await _get_device_or_404(db, id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    await db.flush()
    await db.refresh(device)
    return DeviceRead.model_validate(device)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    device = await _get_device_or_404(db, id)
    await db.delete(device)


@router.post("/{id}/poll")
async def poll_device(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    engine = KPIEngine(SNMPEngine(), async_session_factory)
    kpis_written = await engine.poll_device(device, snmp_cred)
    return {"kpis_written": len(kpis_written)}


@router.post("/{id}/discover-neighbors")
async def discover_neighbors(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    snmp = SNMPEngine()
    lldp = await snmp.discover_lldp_neighbors(device.ip_address, snmp_cred)
    cdp = await snmp.discover_cdp_neighbors(device.ip_address, snmp_cred)
    return lldp + cdp


@router.get("/{id}/managed-interfaces", response_model=list[ManagedInterfaceRead])
async def get_managed_interfaces(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ManagedInterfaceRead]:
    """Return persisted normalized Interface records for service/topology membership."""
    await _get_device_or_404(db, id)
    result = await db.execute(
        select(Interface)
        .where(Interface.device_id == id)
        .order_by(Interface.if_index.asc().nullslast(), Interface.name)
    )
    return [ManagedInterfaceRead.model_validate(interface) for interface in result.scalars().all()]


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

    profile = _chassis_profile_for_device(device, device.inventory)
    if profile is None:
        raise HTTPException(status_code=404, detail="No chassis profile is available for this device")

    physical_result = await db.execute(
        select(PhysicalInventoryComponent)
        .where(PhysicalInventoryComponent.device_id == id)
        .order_by(PhysicalInventoryComponent.physical_index.asc())
    )
    physical_components = list(physical_result.scalars().all())
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


@router.get("/{id}/interfaces", response_model=list[InterfaceRead])
async def get_interfaces(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[InterfaceRead]:
    """Fetch live IF-MIB interface rows for a device via SNMP."""
    device = await _get_device_or_404(db, id)
    snmp_cred = _build_snmp_cred(device)
    snmp = SNMPEngine()
    rows = await snmp.get_interfaces(device.ip_address, snmp_cred)
    return [
        InterfaceRead(
            if_index=row.if_index,
            descr=row.descr,
            type=row.type_,
            speed=row.speed,
            admin_status=row.admin_status,
            oper_status=row.oper_status,
            in_octets=row.in_octets,
            out_octets=row.out_octets,
            in_errors=row.in_errors,
            out_errors=row.out_errors,
            alias=row.alias,
            phys_address=row.phys_address,
        )
        for row in sorted(rows.values(), key=lambda item: item.if_index)
    ]


@router.get("/{id}/inventory")
async def get_inventory(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Called for its side-effect: raises HTTP 404 when the device id is unknown.
    _ = await _get_device_or_404(db, id)
    result = await db.execute(select(Inventory).where(Inventory.device_id == id))
    inv = result.scalar_one_or_none()
    return inv


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
