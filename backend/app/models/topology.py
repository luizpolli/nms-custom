"""Topology models — nodes and links for network topology."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TopologyNode(Base):
    """Node in the network topology graph."""

    __tablename__ = "topology_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position_x: Mapped[float | None] = mapped_column(nullable=True)
    position_y: Mapped[float | None] = mapped_column(nullable=True)
    # Renamed from `metadata` to avoid clash with SQLAlchemy DeclarativeBase.metadata
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    device = relationship("Device", lazy="selectin")

    def __repr__(self) -> str:
        return f"<TopologyNode {self.node_id}>"


class TopologyLink(Base):
    """Link/edge in the network topology graph."""

    __tablename__ = "topology_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topology_nodes.id"))
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("topology_nodes.id"))
    source_interface: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_interface: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discovery_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    def __repr__(self) -> str:
        return f"<TopologyLink {self.source_node_id} → {self.target_node_id}>"
