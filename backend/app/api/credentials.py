"""Credential API routes."""

from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db
from app.models.credential import Credential
from app.schemas.credential import CredentialCreate, CredentialRead, CredentialUpdate
from app.security.crypto import CredentialVault

router = APIRouter()
settings = Settings()


async def _get_or_404(db: AsyncSession, cred_id: uuid.UUID) -> Credential:
    result = await db.execute(select(Credential).where(Credential.id == cred_id))
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    return cred


def _to_read(cred: Credential) -> CredentialRead:
    return CredentialRead.model_validate(
        {**{c.name: getattr(cred, c.name) for c in cred.__table__.columns},
         "has_secret": bool(cred.auth_key)}
    )


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CredentialRead]:
    result = await db.execute(select(Credential))
    return [_to_read(c) for c in result.scalars().all()]


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialRead:
    data = body.model_dump(exclude={"secret", "enc_secret"})
    cred = Credential(**data, auth_key="", enc_key=None)
    db.add(cred)
    await db.flush()  # generate id
    vault = CredentialVault.from_settings(settings)
    cred.auth_key = vault.encrypt(body.secret.get_secret_value(), cred.id.bytes)
    if body.enc_secret:
        cred.enc_key = vault.encrypt(body.enc_secret.get_secret_value(), cred.id.bytes)
    await db.flush()
    await db.refresh(cred)
    return _to_read(cred)


@router.get("/{id}", response_model=CredentialRead)
async def get_credential(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialRead:
    cred = await _get_or_404(db, id)
    return _to_read(cred)


@router.patch("/{id}", response_model=CredentialRead)
async def update_credential(
    id: uuid.UUID,
    body: CredentialUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CredentialRead:
    cred = await _get_or_404(db, id)
    data = body.model_dump(exclude_unset=True, exclude={"secret", "enc_secret"})
    for field, value in data.items():
        setattr(cred, field, value)
    vault = CredentialVault.from_settings(settings)
    if body.secret is not None:
        cred.auth_key = vault.encrypt(body.secret.get_secret_value(), cred.id.bytes)
    if body.enc_secret is not None:
        cred.enc_key = vault.encrypt(body.enc_secret.get_secret_value(), cred.id.bytes)
    await db.flush()
    await db.refresh(cred)
    return _to_read(cred)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    cred = await _get_or_404(db, id)
    await db.delete(cred)
