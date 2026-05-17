"""Device API routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel, Field

from app.config import Settings
from app.database import async_session_factory, get_db
from app.models.credential import Credential
from app.models.device import Device
from app.models.inventory import Inventory
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate
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
    name: str = Field(..., max_length=255)
    host: str = Field(..., max_length=45)
    vendor: str = Field(..., max_length=100)
    user: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1)
    model: Optional[str] = Field(None, max_length=255)
    site: Optional[str] = Field(None, max_length=255)
    tags: list[str] = Field(default_factory=list)


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
            existing = await db.execute(select(Device).where(Device.ip_address == row.host))
            if existing.scalar_one_or_none() is not None:
                raise ValueError(f"device with IP {row.host} already exists")

            cred = Credential(
                name=f"{row.name}-cred",
                hostname=row.host,
                username=row.user,
                auth_key="",
                protocol="snmp",
                snmp_version="v2c",
                port=161,
            )
            db.add(cred)
            await db.flush()
            cred.auth_key = vault.encrypt(row.password, cred.id.bytes)

            device = Device(
                name=row.name,
                ip_address=row.host,
                device_type="router",
                vendor=row.vendor,
                model=row.model,
                location=row.site,
                site_id=row.site,
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
            failed.append(BulkImportFailure(row=idx, name=row.name, error=str(exc)))

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
