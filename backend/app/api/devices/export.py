"""EPNM-style CSV export of managed devices."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.devices.common import router, settings
from app.database import get_db
from app.models.credential import Credential
from app.models.device import Device
from app.models.inventory import Inventory
from app.security.auth import PERM_COMMANDS_EXPORT, Principal, require_command_permission
from app.security.crypto import CredentialVault

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
