"""Pydantic v2 schemas for KPI."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class KPIBase(BaseModel):
    device_id: uuid.UUID
    kpi_type: str = Field(..., max_length=50)
    metric_name: str | None = Field(None, max_length=255)
    technology: str | None = Field(None, max_length=50)
    value: float
    unit: str | None = Field(None, max_length=20)
    kpi_area: str | None = Field(None, max_length=50)
    source_type: str = Field("snmp", max_length=30)
    object_type: str = Field("device", max_length=50)
    object_id: str | None = Field(None, max_length=255)
    quality: str = Field("good", max_length=30)
    labels: dict[str, Any] | None = None
    # API field remains `metadata`; ORM maps DB column to KPI.meta to avoid Base.metadata collision.
    kpi_metadata: dict[str, Any] | None = Field(None, alias="metadata")
    timestamp: datetime


class KPICreate(KPIBase):
    pass


class KPIUpdate(BaseModel):
    value: float | None = None
    unit: str | None = None
    kpi_area: str | None = None
    metric_name: str | None = None
    source_type: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    quality: str | None = None
    labels: dict[str, Any] | None = None
    kpi_metadata: dict[str, Any] | None = Field(None, alias="metadata")


class KPIRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    device_id: uuid.UUID
    kpi_type: str
    metric_name: str | None = None
    technology: str | None = None
    value: float
    unit: str | None = None
    kpi_area: str | None = None
    source_type: str = "snmp"
    object_type: str = "device"
    object_id: str | None = None
    quality: str = "good"
    labels: dict[str, Any] | None = None
    # API field remains `metadata`; ORM maps DB column to KPI.meta to avoid Base.metadata collision.
    kpi_metadata: dict[str, Any] | None = Field(None, alias="metadata")
    timestamp: datetime


class KPIAggregate(BaseModel):
    kpi_type: str
    device_id: uuid.UUID
    avg_value: float
    min_value: float
    max_value: float
    count: int
    since: datetime
    until: datetime
