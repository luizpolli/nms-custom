"""MIB model — custom or uploaded MIB file metadata.

P2 provenance fields
--------------------
- ``source_url``      – optional URL the MIB was fetched from (e.g. Cisco MIB
                        Locator, vendor FTP, RFC mirror). Informational only.
- ``uploader``        – identity of the principal that uploaded the file (API
                        key subject or username). Populated automatically by
                        the upload endpoint.
- ``sha256_checksum`` – hex-encoded SHA-256 digest of the raw uploaded bytes.
                        Computed at upload time so subsequent tamper checks can
                        re-verify the stored file against this value.
- ``checksum_verified``  – True when the uploader also supplied an *expected*
                           checksum that matched the computed digest. False
                           (default) when no expected checksum was provided.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MIB(Base):
    """Stored MIB file metadata."""

    __tablename__ = "mibs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    oid_root: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")

    # --- P2 provenance fields -------------------------------------------
    # Optional URL pointing to the authoritative source of this MIB file.
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Principal that uploaded the file (API-key subject or username).
    uploader: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # SHA-256 hex digest of the raw file bytes at upload time.
    sha256_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # True when the uploader provided a matching expected checksum.
    checksum_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<MIB {self.name} (OID: {self.oid_root})>"
