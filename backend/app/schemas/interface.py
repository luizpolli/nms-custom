"""Pydantic schemas for normalized Interface records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InterfaceBase(BaseModel):
    device_id: uuid.UUID
    if_index: int | None = None
    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=512)
    alias: str | None = Field(None, max_length=512)
    mac_address: str | None = Field(None, max_length=64)
    admin_status: str | None = Field(None, max_length=30)
    oper_status: str | None = Field(None, max_length=30)
    speed_bps: int | None = None
    interface_type: str | None = Field(None, max_length=100)
    role: str | None = Field(None, max_length=100)
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="metadata_json")
    discovered_at: datetime | None = None


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    if_index: int | None = None
    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=512)
    alias: str | None = Field(None, max_length=512)
    mac_address: str | None = Field(None, max_length=64)
    admin_status: str | None = Field(None, max_length=30)
    oper_status: str | None = Field(None, max_length=30)
    speed_bps: int | None = None
    interface_type: str | None = Field(None, max_length=100)
    role: str | None = Field(None, max_length=100)
    metadata: dict[str, Any] | None = None
    discovered_at: datetime | None = None


class InterfaceRead(InterfaceBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

