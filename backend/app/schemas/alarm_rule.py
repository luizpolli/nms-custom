"""Schemas for customer alarm customization rules."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AlarmRuleSource = Literal["snmp_trap", "syslog", "event", "any"]
AlarmRuleMatchField = Literal["trap_oid", "event_type", "message", "source_host", "category"]
AlarmRuleMatchOperator = Literal["equals", "starts_with", "contains", "regex"]
AlarmRuleSeverity = Literal["critical", "major", "minor", "warning", "info", "clear"]


class AlarmRuleBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    enabled: bool = True
    priority: int = Field(100, ge=0, le=9999)
    source_type: AlarmRuleSource = "snmp_trap"
    match_field: AlarmRuleMatchField = "trap_oid"
    match_operator: AlarmRuleMatchOperator = "equals"
    match_pattern: str = Field(..., min_length=1, max_length=512)
    severity: AlarmRuleSeverity = "info"
    category: str | None = Field(None, max_length=30)
    event_type: str | None = Field(None, max_length=100)
    message_template: str | None = None
    correlation_key_template: str | None = Field(None, max_length=255)
    auto_clear: bool = False


class AlarmRuleCreate(AlarmRuleBase):
    pass


class AlarmRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    enabled: bool | None = None
    priority: int | None = Field(None, ge=0, le=9999)
    source_type: AlarmRuleSource | None = None
    match_field: AlarmRuleMatchField | None = None
    match_operator: AlarmRuleMatchOperator | None = None
    match_pattern: str | None = Field(None, min_length=1, max_length=512)
    severity: AlarmRuleSeverity | None = None
    category: str | None = Field(None, max_length=30)
    event_type: str | None = Field(None, max_length=100)
    message_template: str | None = None
    correlation_key_template: str | None = Field(None, max_length=255)
    auto_clear: bool | None = None


class AlarmRuleRead(AlarmRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
