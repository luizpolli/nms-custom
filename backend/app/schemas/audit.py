"""Pydantic schemas for persistent audit logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor: str | None = Field(None, max_length=255)
    action: str = Field(..., max_length=100)
    object_type: str | None = Field(None, max_length=100)
    object_id: str | None = Field(None, max_length=255)
    outcome: str = Field("success", max_length=30)
    source_ip: str | None = Field(None, max_length=64)
    trace_id: str | None = Field(None, max_length=64)
    message: str | None = None
    details: dict[str, Any] | None = None


class AuditLogRead(AuditLogCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime

