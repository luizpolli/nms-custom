"""StarOS bulkstats ingestion models: raw samples, counter catalog, ingestion stats.

Mirrors the telemetry split in app/models/telemetry.py: a high-volume,
short-retention raw table (every counter from every parsed file) plus a
catalog that decides which (group, field) pairs get promoted into the
shared `kpis` table for unified dashboards/alarms. Without that split, a
single 15-minute bulkstats file (observed: ~4,700 lines x ~20-50 fields)
would flood the kpis hypertable shared with SNMP/gNMI sources.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class BulkstatsCounterCatalog(Base):
    """Catalog mapping (group, field_name) to a normalized KPI promotion.

    Only rows with enabled=True get mirrored into the kpis table during
    ingestion; everything else stays available in bulkstats_raw_samples.
    """

    __tablename__ = "bulkstats_counter_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kpi_type: Mapped[str] = mapped_column(String(50), nullable=False, default="bulkstats")
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False, default="bulkstats-instance")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        Index("ix_bulkstats_catalog_group_field", "group", "field_name", unique=True),
    )


class BulkstatsRawSample(Base):
    """One parsed counter value from a bulkstats data file (high volume, short retention)."""

    __tablename__ = "bulkstats_raw_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    source_file: Mapped[str] = mapped_column(String(512), nullable=False)
    group: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    labels: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        Index("ix_bulkstats_raw_device_timestamp", "device_id", "timestamp"),
        Index("ix_bulkstats_raw_group_field_timestamp", "group", "field_name", "timestamp"),
    )


class BulkstatsIngestionStat(Base):
    """Per-source-ip ingestion health counters."""

    __tablename__ = "bulkstats_ingestion_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_ip: Mapped[str] = mapped_column(String(45), nullable=False, unique=True, index=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    files_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unmatched_device: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_file_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bounded rolling window of recently pulled remote filenames (active-pull
    # collector only) so a re-poll of the same remote directory doesn't
    # re-download/re-ingest a file already fetched. See pull_collector.py.
    pulled_filenames: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)
