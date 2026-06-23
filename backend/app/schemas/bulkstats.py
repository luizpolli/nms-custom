"""Pydantic schemas for the bulkstats counter catalog API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BulkstatsCounterCatalogCreate(BaseModel):
    group: str = Field(..., max_length=100)
    field_name: str = Field(..., max_length=255)
    metric_name: str = Field(..., max_length=255)
    unit: str | None = Field(None, max_length=20)
    object_type: str = Field("bulkstats-instance", max_length=50)
    enabled: bool = True


class BulkstatsCounterCatalogUpdate(BaseModel):
    enabled: bool


class BulkstatsCounterCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group: str
    field_name: str
    metric_name: str
    unit: str | None = None
    object_type: str
    enabled: bool
    created_at: datetime


class BulkstatsIngestionStatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_ip: str
    device_id: uuid.UUID | None = None
    files_processed: int
    lines_parsed: int
    lines_failed: int
    unmatched_device: bool
    last_error: str | None = None
    last_file_at: datetime | None = None
    updated_at: datetime
