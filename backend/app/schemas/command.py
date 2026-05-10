"""Pydantic v2 schemas for Command."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CommandBase(BaseModel):
    device_id: uuid.UUID
    name: str = Field(..., max_length=255)
    cli_command: str
    output_path: Optional[str] = Field(None, max_length=500)
    last_output: Optional[str] = None
    meta: Optional[dict] = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class CommandCreate(CommandBase):
    pass


class CommandUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    cli_command: Optional[str] = None
    output_path: Optional[str] = None
    last_output: Optional[str] = None
    meta: Optional[dict] = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class CommandRead(CommandBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
