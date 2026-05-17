"""Pydantic v2 schemas for MIB."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MIBBase(BaseModel):
    name: str = Field(..., max_length=255)
    oid_root: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    file_path: Optional[str] = Field(None, max_length=500)
    status: str = Field("active", max_length=20)


class MIBCreate(MIBBase):
    pass


class MIBUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    oid_root: Optional[str] = None
    description: Optional[str] = None
    file_path: Optional[str] = None
    status: Optional[str] = None


class MIBRead(MIBBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MIBNotificationRead(BaseModel):
    name: str
    oid: Optional[str] = None
    objects: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class MIBSummaryRead(BaseModel):
    module_name: Optional[str] = None
    module_identity_oid: Optional[str] = None
    notifications: list[MIBNotificationRead] = Field(default_factory=list)
