"""Pydantic v2 schemas for Alarm."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AlarmBase(BaseModel):
    device_id: Optional[uuid.UUID] = None
    source_host: str = Field(..., max_length=255)
    severity: str = Field(..., max_length=20)
    category: str = Field(..., max_length=30)
    event_type: str = Field(..., max_length=100)
    message: str
    trap_oid: Optional[str] = Field(None, max_length=255)
    raw_varbinds: Optional[dict] = None
    correlation_key: str = Field(..., max_length=255)
    dedup_key: Optional[str] = Field(None, max_length=255)
    correlation_group_id: Optional[uuid.UUID] = None
    root_alarm_id: Optional[uuid.UUID] = None
    source_type: str = Field("trap", max_length=30)
    object_type: Optional[str] = Field(None, max_length=50)
    object_id: Optional[str] = Field(None, max_length=255)
    state: str = Field("active", max_length=20)
    first_seen: datetime
    last_seen: datetime
    cleared_at: Optional[datetime] = None
    ack_by: Optional[str] = Field(None, max_length=255)
    occurrence_count: int = 1


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(BaseModel):
    severity: Optional[str] = None
    category: Optional[str] = None
    event_type: Optional[str] = None
    message: Optional[str] = None
    state: Optional[str] = None
    dedup_key: Optional[str] = None
    correlation_group_id: Optional[uuid.UUID] = None
    root_alarm_id: Optional[uuid.UUID] = None
    source_type: Optional[str] = None
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    last_seen: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    ack_by: Optional[str] = None
    occurrence_count: Optional[int] = None


class AlarmRead(AlarmBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime


class AlarmAck(BaseModel):
    by_user: str


class AlarmSummary(BaseModel):
    critical: int = 0
    major: int = 0
    minor: int = 0
    warning: int = 0
    info: int = 0
