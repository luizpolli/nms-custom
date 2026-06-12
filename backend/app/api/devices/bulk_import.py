"""Bulk CSV import of devices with per-row credential creation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, status
from loguru import logger
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.devices.common import router, settings
from app.database import get_db
from app.models.credential import Credential
from app.models.device import Device
from app.security.crypto import CredentialVault


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
