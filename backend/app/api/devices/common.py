"""Shared helpers for device API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.device import Device
from app.security.crypto import CredentialVault
from app.services.snmp.poller import SNMPCredential

settings = Settings()

# Shared router decorated by all device submodules. Registration order is the
# import order in app/api/devices/__init__.py — literal paths must register
# before the "/{id}" routes so they are not shadowed by the UUID parameter.
router = APIRouter()


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
