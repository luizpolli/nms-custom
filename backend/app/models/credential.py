"""Credential model — encrypted device credentials."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Credential(Base):
    """Encrypted credential store for device access."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_key: Mapped[str] = mapped_column(String(512), nullable=False)
    enc_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    protocol: Mapped[str] = mapped_column(String(10), default="snmp")
    snmp_version: Mapped[str] = mapped_column(String(5), default="v2c")
    port: Mapped[int] = mapped_column(Integer, default=161)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    # Relationships
    devices = relationship("Device", back_populates="credential", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Credential {self.name} ({self.hostname})>"
