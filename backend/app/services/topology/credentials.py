"""Helpers for topology SNMP credential lookup."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.credential import Credential
from app.models.device import Device
from app.security.crypto import CredentialVault
from app.services.snmp.poller import SNMPCredential


def _to_snmp_credential(credential: Credential, vault: CredentialVault) -> SNMPCredential:
    auth_key = vault.decrypt(credential.auth_key, credential.id.bytes)
    return SNMPCredential(
        version=credential.snmp_version,
        community=auth_key,
        user=credential.username,
        auth_protocol="SHA" if credential.snmp_version == "v3" and auth_key else None,
        auth_key=auth_key if credential.snmp_version == "v3" else None,
        priv_protocol="AES128" if credential.snmp_version == "v3" and credential.enc_key else None,
        priv_key=vault.decrypt(credential.enc_key, credential.id.bytes) if credential.enc_key else None,
        port=credential.port,
    )


async def build_credentials_map(
    session: AsyncSession,
    devices: list[Device],
    settings: Settings | None = None,
) -> dict[uuid.UUID, SNMPCredential]:
    """Return SNMP credentials keyed by both device ID and credential ID."""
    credential_ids = {device.credential_id for device in devices if device.credential_id}
    if not credential_ids:
        return {}

    result = await session.execute(select(Credential).where(Credential.id.in_(credential_ids)))
    credentials = {credential.id: credential for credential in result.scalars().all()}
    vault = CredentialVault.from_settings(settings or Settings())

    mapped: dict[uuid.UUID, SNMPCredential] = {}
    for device in devices:
        if not device.credential_id:
            continue
        credential = credentials.get(device.credential_id)
        if not credential:
            continue
        snmp_credential = _to_snmp_credential(credential, vault)
        mapped[device.id] = snmp_credential
        mapped[credential.id] = snmp_credential
    return mapped
