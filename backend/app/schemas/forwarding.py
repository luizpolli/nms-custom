"""Schemas for event forwarding targets."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ForwardingProtocol = Literal["syslog_udp", "syslog_tcp", "snmp_trap", "http_webhook"]
ForwardingEventType = Literal["trap", "syslog", "telemetry", "alarm"]
ForwardingSeverity = Literal["critical", "major", "minor", "warning", "info"]

_HOST_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


class ForwardingTargetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    protocol: ForwardingProtocol
    target_host: str = Field(..., min_length=1, max_length=255)
    target_port: int = Field(..., ge=1, le=65535)
    event_types: list[ForwardingEventType] = Field(default_factory=list)
    severity_filter: ForwardingSeverity | None = None
    enabled: bool = True

    @field_validator("name", "target_host")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("target_host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        if not _HOST_PATTERN.match(value) or ".." in value:
            raise ValueError("target_host must be a hostname or IP address without spaces")
        return value

    @field_validator("event_types")
    @classmethod
    def validate_event_types(cls, value: list[ForwardingEventType]) -> list[ForwardingEventType]:
        if not value:
            raise ValueError("Select at least one event type")
        return list(dict.fromkeys(value))


class ForwardingTargetCreate(ForwardingTargetBase):
    pass


class ForwardingTargetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    protocol: ForwardingProtocol | None = None
    target_host: str | None = Field(None, min_length=1, max_length=255)
    target_port: int | None = Field(None, ge=1, le=65535)
    event_types: list[ForwardingEventType] | None = None
    severity_filter: ForwardingSeverity | None = None
    enabled: bool | None = None

    @field_validator("name", "target_host")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("target_host")
    @classmethod
    def validate_optional_host(cls, value: str | None) -> str | None:
        if value is not None and (not _HOST_PATTERN.match(value) or ".." in value):
            raise ValueError("target_host must be a hostname or IP address without spaces")
        return value

    @field_validator("event_types")
    @classmethod
    def validate_optional_event_types(
        cls, value: list[ForwardingEventType] | None
    ) -> list[ForwardingEventType] | None:
        if value is not None and not value:
            raise ValueError("Select at least one event type")
        return list(dict.fromkeys(value)) if value is not None else None


class ForwardingTargetRead(ForwardingTargetBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ForwardingTestResult(BaseModel):
    ok: bool
    message: str
