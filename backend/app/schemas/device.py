"""Pydantic v2 schemas for Device."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    name: str = Field(..., max_length=255)
    ip_address: str = Field(..., max_length=45)
    device_type: str = Field(..., max_length=50)
    model: str | None = Field(None, max_length=255)
    vendor: str | None = Field(None, max_length=100)
    os_type: str | None = Field(None, max_length=100)
    software_version: str | None = Field(None, max_length=255)
    status: str = Field("unknown", max_length=20)
    location: str | None = Field(None, max_length=255)
    site_id: str | None = Field(None, max_length=255)
    role: str | None = Field(None, max_length=100)
    lifecycle_state: str = Field("active", max_length=50)
    platform_family: str | None = Field(None, max_length=100)
    mgmt_vrf: str | None = Field(None, max_length=100)
    snmp_enabled: bool = True
    ssh_enabled: bool = False
    telemetry_enabled: bool = False
    tags: list[str] = Field(default_factory=list)
    credential_id: uuid.UUID | None = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    ip_address: str | None = Field(None, max_length=45)
    device_type: str | None = Field(None, max_length=50)
    model: str | None = None
    vendor: str | None = None
    os_type: str | None = None
    software_version: str | None = None
    status: str | None = None
    location: str | None = None
    site_id: str | None = None
    role: str | None = None
    lifecycle_state: str | None = None
    platform_family: str | None = None
    mgmt_vrf: str | None = None
    snmp_enabled: bool | None = None
    ssh_enabled: bool | None = None
    telemetry_enabled: bool | None = None
    tags: list[str] | None = None
    credential_id: uuid.UUID | None = None


class DeviceRead(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
