"""CommandRun model — persistent history of command executions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_STDOUT_MAX = 65536  # 64 KB


class CommandRun(Base):
    """One execution record for a saved or ad-hoc command."""

    __tablename__ = "command_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")

    command = relationship("Command", foreign_keys=[command_id], lazy="selectin")
    device = relationship("Device", foreign_keys=[device_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<CommandRun {self.id} cmd={self.command_id} dev={self.device_id} exit={self.exit_status}>"
