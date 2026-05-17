"""Credential model — encrypted device credentials."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    assignments = relationship("CredentialAssignment", back_populates="credential", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Credential {self.name} ({self.hostname})>"


class CredentialAssignment(Base):
    """Explicit mapping of credential profiles to devices and access purposes."""

    __tablename__ = "credential_assignments"
    __table_args__ = (
        UniqueConstraint("device_id", "credential_id", "purpose", name="uq_credential_assignment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="primary")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    device = relationship("Device", back_populates="credential_assignments", lazy="selectin")
    credential = relationship("Credential", back_populates="assignments", lazy="selectin")

    def __repr__(self) -> str:
        return f"<CredentialAssignment device_id={self.device_id} purpose={self.purpose}>"
