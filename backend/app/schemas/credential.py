"""Pydantic v2 schemas for Credential.

SECURITY: auth_key / enc_key are NEVER returned in CredentialRead.
           On create/update the caller supplies plaintext `secret` (SecretStr);
           the route layer encrypts it and stores ciphertext in auth_key.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CredentialBase(BaseModel):
    name: str = Field(..., max_length=255)
    hostname: str = Field(..., max_length=255)
    username: str = Field(..., max_length=255)
    protocol: str = Field("snmp", max_length=10)
    snmp_version: str = Field("v2c", max_length=5)
    port: int = Field(161, ge=1, le=65535)


class CredentialCreate(CredentialBase):
    secret: SecretStr = Field(..., description="Plaintext credential; will be encrypted at rest.")
    enc_secret: SecretStr | None = Field(None, description="Optional enc key (SNMPv3).")


class CredentialUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    hostname: str | None = Field(None, max_length=255)
    username: str | None = Field(None, max_length=255)
    protocol: str | None = None
    snmp_version: str | None = None
    port: int | None = Field(None, ge=1, le=65535)
    secret: SecretStr | None = Field(None, description="New plaintext secret; triggers re-encryption.")
    enc_secret: SecretStr | None = None


class CredentialRead(CredentialBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    has_secret: bool = Field(..., description="True when auth_key is populated.")
    created_at: datetime
    updated_at: datetime
