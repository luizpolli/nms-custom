"""Interface model — normalized managed interface identity."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Interface(Base):
    """Stable interface record used by KPI, topology, alarms, and inventory."""

    __tablename__ = "interfaces"
    __table_args__ = (
        Index("ix_interfaces_device_ifindex", "device_id", "if_index", unique=True),
        Index("ix_interfaces_device_name", "device_id", "name"),
        Index("ix_interfaces_oper_status", "oper_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True
    )
    if_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    alias: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    admin_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    oper_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    speed_bps: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    interface_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, onupdate=datetime.now
    )

    device = relationship("Device", back_populates="interfaces", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Interface {self.name} device_id={self.device_id}>"

