"""Pydantic schemas for normalized Interface records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class InterfaceBase(BaseModel):
    device_id: uuid.UUID
    if_index: Optional[int] = None
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=512)
    alias: Optional[str] = Field(None, max_length=512)
    mac_address: Optional[str] = Field(None, max_length=64)
    admin_status: Optional[str] = Field(None, max_length=30)
    oper_status: Optional[str] = Field(None, max_length=30)
    speed_bps: Optional[int] = None
    interface_type: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    metadata: Optional[dict[str, Any]] = Field(default=None, validation_alias="metadata_json")
    discovered_at: Optional[datetime] = None


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    if_index: Optional[int] = None
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=512)
    alias: Optional[str] = Field(None, max_length=512)
    mac_address: Optional[str] = Field(None, max_length=64)
    admin_status: Optional[str] = Field(None, max_length=30)
    oper_status: Optional[str] = Field(None, max_length=30)
    speed_bps: Optional[int] = None
    interface_type: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    metadata: Optional[dict[str, Any]] = None
    discovered_at: Optional[datetime] = None


class InterfaceRead(InterfaceBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

