"""KPI model — time-series key performance indicator data."""

import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KPI(Base):
    """Time-series KPI measurement for a device."""

    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"))
    kpi_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    technology: Mapped[str | None] = mapped_column(String(50), nullable=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kpi_area: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="snmp")
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, default="device")
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    quality: Mapped[str] = mapped_column(String(30), nullable=False, default="good")
    # Renamed from `metadata` to avoid clash with SQLAlchemy DeclarativeBase.metadata
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    device = relationship("Device", back_populates="kpis", lazy="selectin")

    __table_args__ = (
        Index("ix_kpis_device_timestamp", "device_id", "timestamp"),
        Index("ix_kpis_timestamp", "timestamp"),
        Index("ix_kpis_kpi_type", "kpi_type"),
        Index("ix_kpis_object_timestamp", "object_type", "object_id", "timestamp"),
        Index("ix_kpis_source_timestamp", "source_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<KPI {self.kpi_type}={self.value} @ {self.timestamp}>"
