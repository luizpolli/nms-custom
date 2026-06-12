"""ConfigBackup model — device running-config snapshots and golden baselines."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConfigBackup(Base):
    """A point-in-time device configuration snapshot.

    ``kind`` distinguishes regular backups from the golden (compliance
    baseline) config: a device's golden config is the most recent row with
    ``kind='golden'``. ``content_hash`` is the SHA-256 of the NORMALIZED
    content (volatile lines stripped) so identical configs deduplicate even
    when timestamps differ.

    Deliberately no relationship on Device: content is large and Device
    relationships are ``lazy='selectin'`` — eager-loading backups on every
    device query would be pathological.
    """

    __tablename__ = "config_backups"
    __table_args__ = (
        Index("ix_config_backups_device_kind_created", "device_id", "kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="backup")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    collected_by: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    def __repr__(self) -> str:
        return f"<ConfigBackup {self.kind} device_id={self.device_id} hash={self.content_hash[:8]}>"
