"""Schemas for scheduled reports and generated artefacts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReportCadence = Literal[
    "every_5m", "every_15m", "every_1h", "hourly",
    "every_6h", "every_24h", "daily", "weekly",
]


class ReportScheduleBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    report_name: str = Field(..., max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)
    cadence: ReportCadence = "daily"
    enabled: bool = True
    retain_last: int = Field(10, ge=0, le=500)


class ReportScheduleCreate(ReportScheduleBase):
    pass


class ReportScheduleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    report_name: str | None = Field(None, max_length=64)
    params: dict[str, Any] | None = None
    cadence: ReportCadence | None = None
    enabled: bool | None = None
    retain_last: int | None = Field(None, ge=0, le=500)


class ReportScheduleRead(ReportScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class GeneratedReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    schedule_id: uuid.UUID | None
    report_name: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error: str | None
    generated_at: datetime
