"""Service models — logical groupings of devices/interfaces for assurance impact."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Service(Base):
    """A logical service composed of network members (devices/interfaces)."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    members: Mapped[list["ServiceMember"]] = relationship(
        "ServiceMember", back_populates="service", cascade="all, delete-orphan", lazy="selectin"
    )
    upstream_dependencies: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency",
        foreign_keys="ServiceDependency.source_service_id",
        back_populates="source_service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    downstream_dependencies: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency",
        foreign_keys="ServiceDependency.target_service_id",
        back_populates="target_service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Service {self.name}>"


class ServiceDependency(Base):
    """Directed dependency between logical services for blast-radius modeling."""

    __tablename__ = "service_dependencies"
    __table_args__ = (
        UniqueConstraint("source_service_id", "target_service_id", name="uq_service_dependency_edge"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependency_type: Mapped[str] = mapped_column(String(50), nullable=False, default="depends_on")
    direction: Mapped[str] = mapped_column(String(50), nullable=False, default="source_to_target")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    source_service = relationship("Service", foreign_keys=[source_service_id], back_populates="upstream_dependencies")
    target_service = relationship("Service", foreign_keys=[target_service_id], back_populates="downstream_dependencies")

    def __repr__(self) -> str:
        return f"<ServiceDependency {self.source_service_id}->{self.target_service_id}>"


class ServiceMember(Base):
    """Member of a Service — a device or interface contributing to service health."""

    __tablename__ = "service_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True
    )
    interface_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interfaces.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    service: Mapped[Service] = relationship("Service", back_populates="members")
    device = relationship("Device", lazy="selectin")
    interface = relationship("Interface", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ServiceMember service={self.service_id} device={self.device_id} iface={self.interface_id}>"


class ServiceScoreSnapshot(Base):
    """Point-in-time service health snapshot for history/trend visibility."""

    __tablename__ = "service_score_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    base_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dependency_penalty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_state: Mapped[str] = mapped_column(String(32), nullable=False, default="healthy")
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<ServiceScoreSnapshot service={self.service_id} score={self.score} at={self.captured_at}>"
