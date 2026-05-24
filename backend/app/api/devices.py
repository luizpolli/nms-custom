"""Device API routes."""

from __future__ import annotations

import uuid
import csv
import io
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from loguru import logger
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.database import async_session_factory, get_db
from app.models.credential import Credential
from app.models.device import Device
from app.models.interface import Interface
from app.models.inventory import Inventory
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
from app.schemas.interface import InterfaceRead as ManagedInterfaceRead
from app.security.auth import PERM_COMMANDS_EXPORT, Principal, require_command_permission
from app.security.crypto import CredentialVault
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential, SNMPPoller
from app.services.kpi.engine import KPIEngine

router = APIRouter()
settings = Settings()


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
    descr: Optional[str] = None
    type: Optional[int] = None
    speed: Optional[int] = None
    admin_status: Optional[int] = None
    oper_status: Optional[int] = None
    in_octets: Optional[int] = None
    out_octets: Optional[int] = None
    in_errors: Optional[int] = None
    out_errors: Optional[int] = None
    alias: Optional[str] = None
    phys_address: Optional[str] = None


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


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    db: Annotated[AsyncSession, Depends(get_db)],
    q: Optional[str] = None,
    status: Optional[str] = None,
    vendor: Optional[str] = None,
    tag: Optional[str] = None,
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

    name: Optional[str] = Field(None, max_length=255, validation_alias=AliasChoices("name", "device_name"))
    host: Optional[str] = Field(None, max_length=45, validation_alias=AliasChoices("host", "ip_address"))
    vendor: str = Field("cisco", max_length=100)
    user: Optional[str] = Field(None, max_length=255, validation_alias=AliasChoices("user", "cli_username"))
    password: Optional[str] = Field(None, validation_alias=AliasChoices("password", "cli_password", "snmp_community"))
    model: Optional[str] = Field(None, max_length=255)
    site: Optional[str] = Field(None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    device_type: Optional[str] = Field(None, max_length=50)
    licenceLevel: Optional[str] = Field(None, validation_alias=AliasChoices("licenceLevel", "licencelevel", "licence_level"))
    snmp_version: Optional[str] = Field(None, max_length=5)
    snmp_community: Optional[str] = None
    snmp_write_community: Optional[str] = None
    snmp_retries: Optional[int] = None
    snmp_timeout: Optional[int] = None
    snmp_port: Optional[int] = Field(None, ge=1, le=65535)
    protocol: Optional[str] = Field(None, max_length=10)
    cli_port: Optional[int] = Field(None, ge=1, le=65535)
    cli_username: Optional[str] = None
    cli_password: Optional[str] = None
    cli_enable_password: Optional[str] = None
    cli_timeout: Optional[int] = None
    snmpv3_user_name: Optional[str] = Field(None, validation_alias=AliasChoices("snmpv3_user_name", "snmpv3_username"))
    snmpv3_auth_type: Optional[str] = None
    snmpv3_auth_password: Optional[str] = None
    snmpv3_privacy_type: Optional[str] = None
    snmpv3_privacy_password: Optional[str] = None
    http_server: Optional[str] = None
    http_port: Optional[int] = Field(None, ge=1, le=65535)
    http_config_username: Optional[str] = None
    http_config_password: Optional[str] = None
    http_monitor_username: Optional[str] = None
    http_monitor_password: Optional[str] = None
    credential_profile: Optional[str] = Field(None, max_length=255)
    location_groupname: Optional[str] = Field(None, max_length=255)
    user_groupname: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    county: Optional[str] = None
    street: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    room: Optional[str] = None
    longitude: Optional[str] = None
    latitude: Optional[str] = None
    altitude: Optional[str] = None
    assigned_network_role: Optional[str] = Field(None, max_length=100)

    @model_validator(mode="after")
    def validate_required_identity(self) -> "BulkDeviceRow":
        if not self.name:
            raise ValueError("name or device_name is required")
        if not self.host:
            raise ValueError("host or ip_address is required")
        if not self.password and not self.snmp_community and not self.snmpv3_auth_password:
            raise ValueError("password, snmp_community, or snmpv3_auth_password is required")
        return self


def _first_present(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _row_location(row: BulkDeviceRow) -> Optional[str]:
    return _first_present(row.site, row.location_groupname, row.room, row.floor, row.building, row.street, row.city, row.state, row.country, row.region)


def _row_site(row: BulkDeviceRow) -> Optional[str]:
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

    ip_address: Optional[str] = None
    dns_name: Optional[str] = None
    identification: Optional[str] = None
    snmp: Optional[dict] = None
    telnet_ssh: Optional[dict] = None
    http: Optional[dict] = None


class VerifyCredentialsResponse(BaseModel):
    ok: bool
    sys_descr: Optional[str] = None
    error: Optional[str] = None


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
    device = await _get_device_or_404(db, id)
    result = await db.execute(select(Inventory).where(Inventory.device_id == id))
    inv = result.scalar_one_or_none()
    return inv
