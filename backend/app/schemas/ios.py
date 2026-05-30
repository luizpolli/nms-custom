"""Pydantic v2 schemas for IOSVersion."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IOSVersionBase(BaseModel):
    device_id: uuid.UUID
    image_file: str | None = Field(None, max_length=500)
    version: str | None = Field(None, max_length=255)
    platform: str | None = Field(None, max_length=100)
    boot_image: str | None = Field(None, max_length=500)
    uptime_hours: int | None = None
    is_eol: bool = False
    is_eos: bool = False


class IOSVersionCreate(IOSVersionBase):
    pass


class IOSVersionUpdate(BaseModel):
    image_file: str | None = None
    version: str | None = None
    platform: str | None = None
    boot_image: str | None = None
    uptime_hours: int | None = None
    is_eol: bool | None = None
    is_eos: bool | None = None


class IOSVersionRead(IOSVersionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
