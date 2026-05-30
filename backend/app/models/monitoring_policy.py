"""Monitoring policy model inspired by Cisco EPNM policy intervals."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MonitoringPolicy(Base):
    """Customer-managed polling policy for collecting KPI/device information."""

    __tablename__ = "monitoring_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="device_health")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    target_all_devices: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    device_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metric_oids: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)

    def __repr__(self) -> str:
        return f"<MonitoringPolicy {self.name} type={self.policy_type} interval={self.interval_seconds}s>"
