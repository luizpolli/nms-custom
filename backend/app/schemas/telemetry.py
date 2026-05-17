"""Pydantic schemas for telemetry MVP APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TelemetryCollectorCreate(BaseModel):
    name: str = Field(..., max_length=255)
    collector_type: str = Field("gnmi", max_length=50)
    endpoint: str | None = Field(None, max_length=512)
    enabled: bool = True


class TelemetryCollectorRead(TelemetryCollectorCreate):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: str
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TelemetrySensorPathCreate(BaseModel):
    vendor: str = Field("cisco", max_length=100)
    platform_family: str | None = Field(None, max_length=100)
    path: str = Field(..., max_length=512)
    metric_name: str = Field(..., max_length=255)
    kpi_type: str = Field(..., max_length=50)
    unit: str | None = Field(None, max_length=20)
    object_type: str = Field("device", max_length=50)
    enabled: bool = True
    labels: dict | None = None


class TelemetrySensorPathRead(TelemetrySensorPathCreate):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    created_at: datetime


class TelemetrySubscriptionCreate(BaseModel):
    name: str = Field(..., max_length=255)
    path: str = Field(..., max_length=512)
    collector_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    sample_interval_ms: int = Field(60000, ge=1000)
    mode: str = Field("sample", max_length=30)
    enabled: bool = True


class TelemetrySubscriptionRead(TelemetrySubscriptionCreate):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    status: str
    last_sample_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TelemetrySampleIngest(BaseModel):
    collector_id: uuid.UUID | None = None
    subscription_id: uuid.UUID | None = None
    device_id: uuid.UUID
    path: str = Field(..., max_length=512)
    value: float
    unit: str | None = Field(None, max_length=20)
    quality: str = Field("good", max_length=30)
    object_type: str = Field("device", max_length=50)
    object_id: str | None = Field(None, max_length=255)
    labels: dict | None = None
    raw_payload: dict | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TelemetryIngestResult(BaseModel):
    raw_sample_id: int | None = None
    kpi_id: int | None = None
    metric_name: str
    kpi_type: str
    event_published: bool = False


class TelemetryHealth(BaseModel):
    collectors: int
    enabled_collectors: int
    subscriptions: int
    enabled_subscriptions: int
