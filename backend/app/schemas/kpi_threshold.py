"""Schemas for KPI threshold (TCA) definitions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThresholdOperator = Literal["gt", "gte", "lt", "lte"]
ThresholdSeverity = Literal["critical", "major", "minor", "warning", "info"]


class KPIThresholdBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    kpi_type: str = Field(..., max_length=50)
    technology: str | None = Field(None, max_length=50)
    operator: ThresholdOperator = "gt"
    value: float
    clear_value: float | None = None
    severity: ThresholdSeverity = "major"
    consecutive_samples: int = Field(1, ge=1, le=20)
    auto_clear: bool = True
    enabled: bool = True
    device_id: uuid.UUID | None = None


class KPIThresholdCreate(KPIThresholdBase):
    pass


class KPIThresholdUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    kpi_type: str | None = Field(None, max_length=50)
    technology: str | None = Field(None, max_length=50)
    operator: ThresholdOperator | None = None
    value: float | None = None
    clear_value: float | None = None
    severity: ThresholdSeverity | None = None
    consecutive_samples: int | None = Field(None, ge=1, le=20)
    auto_clear: bool | None = None
    enabled: bool | None = None
    device_id: uuid.UUID | None = None


class KPIThresholdRead(KPIThresholdBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
