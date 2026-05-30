"""Pydantic v2 schemas for Alarm."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlarmBase(BaseModel):
    device_id: uuid.UUID | None = None
    source_host: str = Field(..., max_length=255)
    severity: str = Field(..., max_length=20)
    category: str = Field(..., max_length=30)
    event_type: str = Field(..., max_length=100)
    message: str
    trap_oid: str | None = Field(None, max_length=255)
    raw_varbinds: dict | None = None
    correlation_key: str = Field(..., max_length=255)
    dedup_key: str | None = Field(None, max_length=255)
    correlation_group_id: uuid.UUID | None = None
    root_alarm_id: uuid.UUID | None = None
    source_type: str = Field("trap", max_length=30)
    object_type: str | None = Field(None, max_length=50)
    object_id: str | None = Field(None, max_length=255)
    state: str = Field("active", max_length=20)
    first_seen: datetime
    last_seen: datetime
    cleared_at: datetime | None = None
    ack_by: str | None = Field(None, max_length=255)
    occurrence_count: int = 1


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(BaseModel):
    severity: str | None = None
    category: str | None = None
    event_type: str | None = None
    message: str | None = None
    state: str | None = None
    dedup_key: str | None = None
    correlation_group_id: uuid.UUID | None = None
    root_alarm_id: uuid.UUID | None = None
    source_type: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    last_seen: datetime | None = None
    cleared_at: datetime | None = None
    ack_by: str | None = None
    occurrence_count: int | None = None


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
