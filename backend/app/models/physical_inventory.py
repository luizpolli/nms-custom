"""Physical inventory model — ENTITY-MIB component records per device."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PhysicalInventoryComponent(Base):
    """One normalized entPhysicalTable component row for chassis/inventory use."""

    __tablename__ = "physical_inventory_components"
    __table_args__ = (
        Index("ix_physical_inventory_device_index", "device_id", "physical_index", unique=True),
        Index("ix_physical_inventory_device_class", "device_id", "physical_class"),
        Index("ix_physical_inventory_serial", "serial_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    physical_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    vendor_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contained_physical_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    physical_class: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_rel_pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hardware_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_fru: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, onupdate=datetime.now
    )

    device = relationship("Device", back_populates="physical_inventory", lazy="selectin")

    def __repr__(self) -> str:
        return f"<PhysicalInventoryComponent device_id={self.device_id} physical_index={self.physical_index}>"
