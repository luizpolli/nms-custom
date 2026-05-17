"""Pydantic schemas for persistent audit logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor: Optional[str] = Field(None, max_length=255)
    action: str = Field(..., max_length=100)
    object_type: Optional[str] = Field(None, max_length=100)
    object_id: Optional[str] = Field(None, max_length=255)
    outcome: str = Field("success", max_length=30)
    source_ip: Optional[str] = Field(None, max_length=64)
    trace_id: Optional[str] = Field(None, max_length=64)
    message: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class AuditLogRead(AuditLogCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime

