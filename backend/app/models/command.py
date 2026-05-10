"""Command model — saved CLI commands for device management."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Command(Base):
    """Saved CLI command associated with a device."""

    __tablename__ = "commands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cli_command: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Renamed from `metadata` to avoid clash with SQLAlchemy DeclarativeBase.metadata
    meta: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    device = relationship("Device", back_populates="commands", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Command {self.name} on device {self.device_id}>"
