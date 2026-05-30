"""Telemetry ingestion models for collectors, subscriptions, sensor paths, and raw samples."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class TelemetryCollector(Base):
    """External or embedded telemetry collector instance."""

    __tablename__ = "telemetry_collectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    collector_type: Mapped[str] = mapped_column(String(50), nullable=False, default="gnmi")
    endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)

    subscriptions = relationship("TelemetrySubscription", back_populates="collector", lazy="selectin")


class TelemetrySensorPath(Base):
    """Catalog mapping vendor/model/path values to normalized KPI metric names."""

    __tablename__ = "telemetry_sensor_paths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor: Mapped[str] = mapped_column(String(100), nullable=False, default="cisco")
    platform_family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    kpi_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, default="device")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        Index("ix_telemetry_sensor_vendor_path", "vendor", "path"),
    )


class TelemetrySubscription(Base):
    """Requested telemetry subscription for a collector/device/path."""

    __tablename__ = "telemetry_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collector_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("telemetry_collectors.id"), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    sample_interval_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=60000)
    mode: Mapped[str] = mapped_column(String(30), nullable=False, default="sample")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    last_sample_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)

    collector = relationship("TelemetryCollector", back_populates="subscriptions", lazy="selectin")

    __table_args__ = (
        Index("ix_telemetry_subscriptions_device_path", "device_id", "path"),
    )


class TelemetryRawSample(Base):
    """Short-retention raw telemetry sample prior to/alongside KPI normalization."""

    __tablename__ = "telemetry_raw_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collector_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("telemetry_collectors.id"), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("telemetry_subscriptions.id"), nullable=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality: Mapped[str] = mapped_column(String(30), nullable=False, default="good")
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, default="device")
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        Index("ix_telemetry_raw_device_timestamp", "device_id", "timestamp"),
        Index("ix_telemetry_raw_path_timestamp", "path", "timestamp"),
    )


class TelemetryIngestionStat(Base):
    """Per-collector ingestion health counters."""

    __tablename__ = "telemetry_ingestion_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    collector_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("telemetry_collectors.id"), nullable=True)
    samples_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dropped_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sample_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)
