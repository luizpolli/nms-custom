"""Pydantic v2 schemas for Command."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommandBase(BaseModel):
    device_id: uuid.UUID
    name: str = Field(..., max_length=255)
    cli_command: str
    output_path: str | None = Field(None, max_length=500)
    last_output: str | None = None
    meta: dict | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class CommandCreate(CommandBase):
    pass


class CommandUpdate(BaseModel):
    device_id: uuid.UUID | None = None
    name: str | None = Field(None, max_length=255)
    cli_command: str | None = None
    output_path: str | None = None
    last_output: str | None = None
    meta: dict | None = Field(None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class CommandRead(CommandBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
