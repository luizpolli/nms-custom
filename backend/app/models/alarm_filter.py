"""Saved alarm filter presets."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SavedAlarmFilter(Base):
    """User-owned alarm filter preset that can optionally be shared."""

    __tablename__ = "saved_alarm_filters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self) -> str:
        return f"<SavedAlarmFilter {self.name} owner={self.owner} public={self.is_public}>"
