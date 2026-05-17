"""Pydantic v2 schemas for KPI."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class KPIBase(BaseModel):
    device_id: uuid.UUID
    kpi_type: str = Field(..., max_length=50)
    metric_name: Optional[str] = Field(None, max_length=255)
    technology: Optional[str] = Field(None, max_length=50)
    value: float
    unit: Optional[str] = Field(None, max_length=20)
    kpi_area: Optional[str] = Field(None, max_length=50)
    source_type: str = Field("snmp", max_length=30)
    object_type: str = Field("device", max_length=50)
    object_id: Optional[str] = Field(None, max_length=255)
    quality: str = Field("good", max_length=30)
    labels: Optional[Dict[str, Any]] = None
    # API field remains `metadata`; ORM maps DB column to KPI.meta to avoid Base.metadata collision.
    kpi_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")
    timestamp: datetime


class KPICreate(KPIBase):
    pass


class KPIUpdate(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    kpi_area: Optional[str] = None
    metric_name: Optional[str] = None
    source_type: Optional[str] = None
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    quality: Optional[str] = None
    labels: Optional[Dict[str, Any]] = None
    kpi_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class KPIRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    device_id: uuid.UUID
    kpi_type: str
    metric_name: Optional[str] = None
    technology: Optional[str] = None
    value: float
    unit: Optional[str] = None
    kpi_area: Optional[str] = None
    source_type: str = "snmp"
    object_type: str = "device"
    object_id: Optional[str] = None
    quality: str = "good"
    labels: Optional[Dict[str, Any]] = None
    # API field remains `metadata`; ORM maps DB column to KPI.meta to avoid Base.metadata collision.
    kpi_metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata")
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
