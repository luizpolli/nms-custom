"""CommandSchedule model — recurring execution of a saved command against device targets."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CommandSchedule(Base):
    """Recurring command execution job."""

    __tablename__ = "command_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    command_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commands.id"), nullable=False)
    # Target spec — either explicit device_ids OR a tag filter (or both)
    device_ids: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Schedule — cron expression e.g. "0 * * * *" or plain interval label
    cron_expr: Mapped[str | None] = mapped_column(String(128), nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)

    command = relationship("Command", foreign_keys=[command_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<CommandSchedule {self.name} cmd={self.command_id} enabled={self.enabled}>"
