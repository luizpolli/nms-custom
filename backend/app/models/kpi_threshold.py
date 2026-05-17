"""KPI threshold model — Threshold Crossing Alert (TCA) definitions.

Inspired by Cisco Prime Performance Manager TCAs: per-KPI numeric thresholds with
direction, severity and optional hysteresis (clear value) for autoclear behaviour.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KPIThreshold(Base):
    """Threshold definition that emits an alarm when a KPI crosses ``value``.

    Comparison operators: ``gt``, ``gte``, ``lt``, ``lte``.
    ``clear_value`` defines the hysteresis level used to clear the alarm.
    """

    __tablename__ = "kpi_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kpi_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    operator: Mapped[str] = mapped_column(String(4), nullable=False, default="gt")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    clear_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="major")
    consecutive_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    auto_clear: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)

    def __repr__(self) -> str:
        return f"<KPIThreshold {self.name} {self.kpi_type} {self.operator} {self.value}>"
