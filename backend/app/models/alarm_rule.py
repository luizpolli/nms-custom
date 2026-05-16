"""Alarm customization rules for traps, syslogs, and internal events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlarmRule(Base):
    """Customer-managed rule that overrides alarm severity or clears alarms."""

    __tablename__ = "alarm_rules"
    __table_args__ = (
        Index("ix_alarm_rules_enabled_priority", "enabled", "priority"),
        Index("ix_alarm_rules_source_type", "source_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # "snmp_trap" | "syslog" | "event" | "any"
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="snmp_trap")
    # "trap_oid" | "event_type" | "message" | "source_host" | "category"
    match_field: Mapped[str] = mapped_column(String(50), nullable=False, default="trap_oid")
    # "equals" | "starts_with" | "contains" | "regex"
    match_operator: Mapped[str] = mapped_column(String(30), nullable=False, default="equals")
    match_pattern: Mapped[str] = mapped_column(String(512), nullable=False)

    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_key_template: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # If true, a matching event clears the correlated active alarm instead of raising one.
    auto_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)

    def __repr__(self) -> str:
        return f"<AlarmRule {self.name} source={self.source_type} severity={self.severity}>"
