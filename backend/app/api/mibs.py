"""MIB API routes."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.mib import MIB
from app.schemas.mib import (
    MIBCreate,
    MIBNotificationRead,
    MIBRead,
    MIBSummaryRead,
    MIBUpdate,
    MIBUploadRequest,
)
from app.security.audit import audit
from app.security.auth import principal_from_presented_key
from app.services.snmp.mib_parser import parse_mib_text

router = APIRouter()

MIB_STORAGE_DIR = Path(settings.mib_storage_dir)


def _safe_mib_filename(filename: str | None) -> str:
    raw = filename or "unnamed.mib"
    name = Path(raw).name
    if name in {"", ".", ".."} or raw != name:
        raise HTTPException(status_code=400, detail="Invalid filename")
    suffix = Path(name).suffix.lower()
    if suffix not in settings.mib_allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported MIB file extension")
    return name


async def _get_or_404(db: AsyncSession, mib_id: uuid.UUID) -> MIB:
    result = await db.execute(select(MIB).where(MIB.id == mib_id))
    mib = result.scalar_one_or_none()
    if mib is None:
        raise HTTPException(status_code=404, detail="MIB not found")
    return mib


@router.get("", response_model=list[MIBRead])
async def list_mibs(db: Annotated[AsyncSession, Depends(get_db)]) -> list[MIBRead]:
    result = await db.execute(select(MIB))
    return [MIBRead.model_validate(m) for m in result.scalars().all()]


@router.post("", response_model=MIBRead, status_code=status.HTTP_201_CREATED)
async def create_mib(
    body: MIBCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MIBRead:
    mib = MIB(**body.model_dump())
    db.add(mib)
    await db.flush()
    await db.refresh(mib)
    return MIBRead.model_validate(mib)


@router.get("/{id}", response_model=MIBRead)
async def get_mib(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MIBRead:
    mib = await _get_or_404(db, id)
    return MIBRead.model_validate(mib)


@router.get("/{id}/summary", response_model=MIBSummaryRead)
async def get_mib_summary(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MIBSummaryRead:
    """Return parsed SMIv2 module/notification metadata for a stored MIB file."""
    mib = await _get_or_404(db, id)
    if not mib.file_path:
        return MIBSummaryRead()
    path = Path(mib.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="MIB file not found")
    summary = parse_mib_text(path.read_text(errors="ignore"))
    return MIBSummaryRead(
        module_name=summary.module_name,
        module_identity_oid=summary.module_identity_oid,
        notifications=[MIBNotificationRead(**n.__dict__) for n in summary.notifications],
    )


@router.patch("/{id}", response_model=MIBRead)
async def update_mib(
    id: uuid.UUID,
    body: MIBUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MIBRead:
    mib = await _get_or_404(db, id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(mib, field, value)
    await db.flush()
    await db.refresh(mib)
    return MIBRead.model_validate(mib)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mib(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    mib = await _get_or_404(db, id)
    await db.delete(mib)


@router.post("/upload", response_model=MIBRead, status_code=status.HTTP_201_CREATED)
async def upload_mib(
    file: UploadFile,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    source_url: Annotated[str | None, Query(max_length=1000, description="Authoritative source URL for this MIB file")] = None,
    expected_sha256: Annotated[str | None, Query(description="Expected hex SHA-256 checksum (64 chars). When provided, the upload is rejected if the digest does not match.")] = None,
) -> MIBRead:
    """Upload a MIB file.

    P2 provenance:
    - Pass ``expected_sha256`` (64-hex chars) to have the server verify the
      file integrity. The upload is rejected with HTTP 422 when the digest
      does not match.
    - Omitting ``expected_sha256`` is allowed but triggers a warning in the
      response headers (``X-MIB-Checksum-Warning``).
    - Pass ``source_url`` to record where the MIB was obtained from.

    Recommended MIB sources (Cisco):
    - https://github.com/cisco/cisco-mibs (GitHub mirror, SHA-verified releases)
    - https://mibs.cloudapps.cisco.com/ITDIT/MIBS/servlet/index (Cisco MIB Locator)
    - Vendor FTP/HTTPS repositories distributed with IOS/XE/XR releases
    """
    # Validate expected_sha256 format if provided
    upload_req = MIBUploadRequest(
        source_url=source_url,
        expected_sha256=expected_sha256,
    )

    MIB_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_mib_filename(file.filename)
    dest = (MIB_STORAGE_DIR / safe_name).resolve()
    storage_root = MIB_STORAGE_DIR.resolve()
    if storage_root not in dest.parents:
        raise HTTPException(status_code=400, detail="Invalid upload path")

    content = await file.read(settings.mib_upload_max_bytes + 1)
    if len(content) > settings.mib_upload_max_bytes:
        raise HTTPException(status_code=413, detail="MIB upload exceeds configured size limit")

    # --- P2 checksum handling -------------------------------------------
    computed_sha256 = hashlib.sha256(content).hexdigest()
    checksum_verified = False
    checksum_warning: str | None = None

    if upload_req.expected_sha256:
        if computed_sha256 != upload_req.expected_sha256:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"SHA-256 checksum mismatch. "
                    f"Expected: {upload_req.expected_sha256}  "
                    f"Computed: {computed_sha256}. "
                    "Upload rejected. Verify the file was not corrupted in transit."
                ),
            )
        checksum_verified = True
    else:
        checksum_warning = (
            "No expected_sha256 checksum was provided. "
            "Consider supplying the checksum from a trusted source to verify file integrity."
        )
    # --------------------------------------------------------------------

    try:
        import aiofiles
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
    except ImportError:
        dest.write_bytes(content)

    summary = parse_mib_text(content.decode(errors="ignore"))
    description = None
    if summary.module_name or summary.notifications:
        description = f"Parsed module {summary.module_name or safe_name}; notifications: {len(summary.notifications)}"

    # Resolve uploader identity from the API key presented in the request.
    presented_key = request.headers.get("x-api-key")
    auth_header = request.headers.get("authorization", "")
    if not presented_key and auth_header.lower().startswith("bearer "):
        presented_key = auth_header[7:].strip()
    uploader_obj = principal_from_presented_key(presented_key)
    uploader_principal: str | None = uploader_obj.subject

    mib = MIB(
        name=safe_name,
        oid_root=summary.module_identity_oid,
        description=description,
        file_path=str(dest),
        status="active",
        source_url=upload_req.source_url,
        sha256_checksum=computed_sha256,
        checksum_verified=checksum_verified,
        uploader=uploader_principal,
    )
    db.add(mib)
    await db.flush()
    await db.refresh(mib)
    audit(
        "mib.upload",
        target=str(mib.id),
        filename=safe_name,
        size=len(content),
        sha256=computed_sha256,
        checksum_verified=checksum_verified,
        source_url=upload_req.source_url,
    )

    read_response = MIBRead.model_validate(mib)
    # Attach warning header when no checksum was supplied so callers can
    # detect the gap without parsing the body.
    if checksum_warning:
        # We return a Response with the header set; since FastAPI serialises
        # the response_model for us, we attach the warning via a custom response.
        import json  # noqa: PLC0415

        from fastapi.responses import JSONResponse  # noqa: PLC0415
        resp = JSONResponse(
            content=json.loads(read_response.model_dump_json()),
            status_code=status.HTTP_201_CREATED,
            headers={"X-MIB-Checksum-Warning": checksum_warning},
        )
        return resp  # type: ignore[return-value]
    return read_response
