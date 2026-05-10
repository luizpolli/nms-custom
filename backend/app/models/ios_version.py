"""IOS version model — device software/IOS version tracking."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class IOSVersion(Base):
    """IOS/software version record for a device."""

    __tablename__ = "ios_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"))
    image_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    boot_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uptime_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_eol: Mapped[bool] = mapped_column(default=False)
    is_eos: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)

    device = relationship("Device", back_populates="ios_versions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<IOSVersion {self.version} on device {self.device_id}>"
