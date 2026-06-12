"""Live SNMP operations: polling, discovery, IF-MIB reads, credential checks."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.devices.common import _build_snmp_cred, _get_device_or_404, router
from app.database import async_session_factory, get_db
from app.services.kpi.engine import KPIEngine
from app.services.snmp.engine import SNMPEngine
from app.services.snmp.poller import SNMPCredential, SNMPPoller


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
