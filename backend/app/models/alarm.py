"""Alarm model — correlated SNMP trap / event records."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Alarm(Base):
    """Correlated network alarm, created from SNMP traps or other event sources."""

    __tablename__ = "alarms"
    __table_args__ = (
        Index("ix_alarms_device_state", "device_id", "state"),
        Index("ix_alarms_correlation_state", "correlation_key", "state"),
        Index("ix_alarms_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True, index=True
    )
    source_host: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # "critical"|"major"|"minor"|"warning"|"info"|"clear"
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    # "link"|"device"|"auth"|"environment"|"performance"|"other"
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    trap_oid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_varbinds: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    correlation_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    root_alarm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("alarms.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="trap")
    object_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # "active"|"cleared"|"acknowledged"
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ack_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )

    device = relationship("Device", lazy="selectin")
    root_alarm = relationship("Alarm", remote_side=[id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<Alarm {self.event_type} {self.severity} src={self.source_host} state={self.state}>"
