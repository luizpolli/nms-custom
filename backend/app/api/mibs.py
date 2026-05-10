"""MIB API routes."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.mib import MIB
from app.schemas.mib import MIBCreate, MIBRead, MIBUpdate

router = APIRouter()

MIB_STORAGE_DIR = Path("/data/mibs")


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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MIBRead:
    MIB_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    dest = MIB_STORAGE_DIR / (file.filename or "unnamed.mib")
    content = await file.read()
    try:
        import aiofiles
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)
    except ImportError:
        dest.write_bytes(content)

    mib = MIB(
        name=file.filename or "unnamed.mib",
        file_path=str(dest),
        status="active",
    )
    db.add(mib)
    await db.flush()
    await db.refresh(mib)
    return MIBRead.model_validate(mib)
