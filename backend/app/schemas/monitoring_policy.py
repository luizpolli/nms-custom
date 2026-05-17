"""Schemas for monitoring policy CRUD and execution."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PolicyType = Literal[
    "device_health",
    "interface_health",
    "custom_mib",
    "optical_sfp",
    "optical_15m",
    "optical_1d",
    "mpls_link_performance",
    "ip_sla",
    "gnss",
    "syslog",
]

ALLOWED_INTERVALS_SECONDS = [60, 300, 900, 3600, 21600, 43200, 86400]


class MonitoringPolicyBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    policy_type: PolicyType = "device_health"
    enabled: bool = True
    interval_seconds: int = Field(300, description="Allowed: 60, 300, 900, 3600, 21600, 43200, 86400")
    target_all_devices: bool = True
    device_ids: list[uuid.UUID] = Field(default_factory=list)
    metric_oids: list[dict] = Field(default_factory=list)
    thresholds: dict = Field(default_factory=dict)

    def model_post_init(self, _context: object) -> None:
        if self.interval_seconds not in ALLOWED_INTERVALS_SECONDS:
            raise ValueError("interval_seconds must be one of 60, 300, 900, 3600, 21600, 43200, 86400")


class MonitoringPolicyCreate(MonitoringPolicyBase):
    pass


class MonitoringPolicyUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    policy_type: PolicyType | None = None
    enabled: bool | None = None
    interval_seconds: int | None = None
    target_all_devices: bool | None = None
    device_ids: list[uuid.UUID] | None = None
    metric_oids: list[dict] | None = None
    thresholds: dict | None = None

    def model_post_init(self, _context: object) -> None:
        if self.interval_seconds is not None and self.interval_seconds not in ALLOWED_INTERVALS_SECONDS:
            raise ValueError("interval_seconds must be one of 60, 300, 900, 3600, 21600, 43200, 86400")


class MonitoringPolicyRead(MonitoringPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class MonitoringPolicyPreset(BaseModel):
    name: str
    policy_type: PolicyType
    interval_seconds: int
    description: str
