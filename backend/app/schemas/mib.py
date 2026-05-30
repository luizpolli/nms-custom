"""Pydantic v2 schemas for MIB.

P2 additions
------------
- ``source_url``         – optional provenance URL (vendor site, RFC mirror, etc.)
- ``expected_sha256``    – upload-time expected checksum (write-only, not stored in DB).
                           When provided, the upload endpoint verifies the computed
                           digest matches and sets ``checksum_verified=True``.
- ``sha256_checksum``    – computed SHA-256 hex digest of the uploaded file (read).
- ``checksum_verified``  – True when expected checksum was provided and matched (read).
- ``uploader``           – identity of the uploading principal (read).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class MIBBase(BaseModel):
    name: str = Field(..., max_length=255)
    oid_root: str | None = Field(None, max_length=100)
    description: str | None = None
    file_path: str | None = Field(None, max_length=500)
    status: str = Field("active", max_length=20)
    source_url: str | None = Field(None, max_length=1000, description="Authoritative source URL for the MIB file")


class MIBCreate(MIBBase):
    pass


class MIBUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    oid_root: str | None = None
    description: str | None = None
    file_path: str | None = None
    status: str | None = None
    source_url: str | None = Field(None, max_length=1000)


class MIBUploadRequest(BaseModel):
    """Optional query/form parameters accepted alongside the file upload."""

    source_url: str | None = Field(None, max_length=1000)
    expected_sha256: str | None = Field(
        None,
        description=(
            "Optional hex-encoded SHA-256 checksum of the uploaded file. "
            "When supplied, the server verifies the digest and rejects the "
            "upload if it does not match. Omitting this field is allowed but "
            "will produce a warning in the response."
        ),
    )

    @field_validator("expected_sha256")
    @classmethod
    def validate_sha256(cls, v: str | None) -> str | None:
        if v is not None and not _SHA256_RE.match(v):
            raise ValueError("expected_sha256 must be a 64-character hex string")
        return v.lower() if v else v


class MIBRead(MIBBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sha256_checksum: str | None = None
    checksum_verified: bool = False
    uploader: str | None = None
    created_at: datetime
    updated_at: datetime


class MIBNotificationRead(BaseModel):
    name: str
    oid: str | None = None
    objects: list[str] = Field(default_factory=list)
    description: str | None = None


class MIBSummaryRead(BaseModel):
    module_name: str | None = None
    module_identity_oid: str | None = None
    notifications: list[MIBNotificationRead] = Field(default_factory=list)
