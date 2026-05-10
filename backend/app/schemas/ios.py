"""Pydantic v2 schemas for IOSVersion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IOSVersionBase(BaseModel):
    device_id: uuid.UUID
    image_file: Optional[str] = Field(None, max_length=500)
    version: Optional[str] = Field(None, max_length=255)
    platform: Optional[str] = Field(None, max_length=100)
    boot_image: Optional[str] = Field(None, max_length=500)
    uptime_hours: Optional[int] = None
    is_eol: bool = False
    is_eos: bool = False


class IOSVersionCreate(IOSVersionBase):
    pass


class IOSVersionUpdate(BaseModel):
    image_file: Optional[str] = None
    version: Optional[str] = None
    platform: Optional[str] = None
    boot_image: Optional[str] = None
    uptime_hours: Optional[int] = None
    is_eol: Optional[bool] = None
    is_eos: Optional[bool] = None


class IOSVersionRead(IOSVersionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
