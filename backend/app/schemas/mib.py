"""Pydantic v2 schemas for MIB."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MIBBase(BaseModel):
    name: str = Field(..., max_length=255)
    oid_root: str | None = Field(None, max_length=100)
    description: str | None = None
    file_path: str | None = Field(None, max_length=500)
    status: str = Field("active", max_length=20)


class MIBCreate(MIBBase):
    pass


class MIBUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    oid_root: str | None = None
    description: str | None = None
    file_path: str | None = None
    status: str | None = None


class MIBRead(MIBBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MIBNotificationRead(BaseModel):
    name: str
    oid: str | None = None
    objects: list[str] = Field(default_factory=list)
    description: str | None = None


class MIBSummaryRead(BaseModel):
    module_name: str | None = None
    module_identity_oid: str | None = None
    notifications: list[MIBNotificationRead] = Field(default_factory=list)
