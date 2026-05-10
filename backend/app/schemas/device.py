"""Pydantic v2 schemas for Device."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DeviceBase(BaseModel):
    name: str = Field(..., max_length=255)
    ip_address: str = Field(..., max_length=45)
    device_type: str = Field(..., max_length=50)
    model: Optional[str] = Field(None, max_length=255)
    vendor: Optional[str] = Field(None, max_length=100)
    os_type: Optional[str] = Field(None, max_length=100)
    status: str = Field("unknown", max_length=20)
    location: Optional[str] = Field(None, max_length=255)
    tags: List[str] = Field(default_factory=list)
    credential_id: Optional[uuid.UUID] = None


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    ip_address: Optional[str] = Field(None, max_length=45)
    device_type: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = None
    vendor: Optional[str] = None
    os_type: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    tags: Optional[List[str]] = None
    credential_id: Optional[uuid.UUID] = None


class DeviceRead(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
