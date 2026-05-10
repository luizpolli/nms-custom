"""Device model — core network device record."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ARRAY, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Device(Base):
    """Network device record (router, switch, firewall, server, etc.)."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, unique=True)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    credential_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # Relationships
    credential = relationship("Credential", back_populates="devices", lazy="selectin")
    inventory = relationship("Inventory", back_populates="device", uselist=False, lazy="selectin")
    kpis = relationship("KPI", back_populates="device", lazy="selectin")
    ios_versions = relationship("IOSVersion", back_populates="device", lazy="selectin")
    commands = relationship("Command", back_populates="device", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Device {self.name} ({self.ip_address})>"
