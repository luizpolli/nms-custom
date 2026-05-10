"""Pydantic v2 schemas for Credential.

SECURITY: auth_key / enc_key are NEVER returned in CredentialRead.
           On create/update the caller supplies plaintext `secret` (SecretStr);
           the route layer encrypts it and stores ciphertext in auth_key.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

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
    enc_secret: Optional[SecretStr] = Field(None, description="Optional enc key (SNMPv3).")


class CredentialUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    hostname: Optional[str] = Field(None, max_length=255)
    username: Optional[str] = Field(None, max_length=255)
    protocol: Optional[str] = None
    snmp_version: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    secret: Optional[SecretStr] = Field(None, description="New plaintext secret; triggers re-encryption.")
    enc_secret: Optional[SecretStr] = None


class CredentialRead(CredentialBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    has_secret: bool = Field(..., description="True when auth_key is populated.")
    created_at: datetime
    updated_at: datetime
