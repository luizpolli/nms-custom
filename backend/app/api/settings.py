"""System settings and local user administration."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.system import AppUser, SystemSetting
from app.security.audit import audit
from app.security.passwords import hash_password

router = APIRouter()
_SECURITY_KEY = "security"


class SecuritySettings(BaseModel):
    https_enabled: bool = False
    https_redirect_enabled: bool = True
    tls_min_version: Literal["TLSv1.2", "TLSv1.3"] = "TLSv1.3"
    tls_cert_file: str = ""
    tls_key_file: str = ""
    tls_ca_file: str = ""
    require_signed_html_certificate: bool = True
    api_auth_enabled: bool = False
    max_parallel_sessions: int = Field(5, ge=1, le=100)
    idle_timeout_minutes: int = Field(30, ge=1, le=1440)
    root_web_login_enabled: bool = False

    @field_validator("tls_cert_file", "tls_key_file", "tls_ca_file")
    @classmethod
    def validate_cert_path(cls, value: str) -> str:
        if value and (".." in value or any(ch in value for ch in "\r\n\x00")):
            raise ValueError("Invalid certificate path")
        return value


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    display_name: str | None = None
    role: str
    user_type: str
    virtual_domain: str | None = None
    enabled: bool
    force_password_change: bool


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, pattern=r"^[A-Za-z0-9_.@-]+$")
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr = Field(..., min_length=12)
    role: Literal["admin", "super_user", "config_manager", "operator", "viewer", "nbi_read", "nbi_write"] = "viewer"
    user_type: Literal["web", "nbi"] = "web"
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool = True
    force_password_change: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr | None = Field(None, min_length=12)
    role: Literal["admin", "super_user", "config_manager", "operator", "viewer", "nbi_read", "nbi_write"] | None = None
    user_type: Literal["web", "nbi"] | None = None
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    force_password_change: bool | None = None


def _defaults() -> SecuritySettings:
    return SecuritySettings(
        https_enabled=settings.https_enabled,
        https_redirect_enabled=settings.https_redirect_enabled,
        tls_min_version=settings.tls_min_version,
        tls_cert_file=settings.tls_cert_file,
        tls_key_file=settings.tls_key_file,
        tls_ca_file=settings.tls_ca_file,
        require_signed_html_certificate=settings.require_signed_html_certificate,
        api_auth_enabled=settings.api_auth_enabled,
        max_parallel_sessions=settings.max_parallel_sessions,
        idle_timeout_minutes=settings.idle_timeout_minutes,
        root_web_login_enabled=settings.root_web_login_enabled,
    )


@router.get("/security", response_model=SecuritySettings)
async def get_security_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> SecuritySettings:
    row = await db.get(SystemSetting, _SECURITY_KEY)
    if not row:
        return _defaults()
    return SecuritySettings(**{**_defaults().model_dump(), **row.value})


@router.patch("/security", response_model=SecuritySettings)
async def update_security_settings(
    body: SecuritySettings,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SecuritySettings:
    if body.https_enabled and (not body.tls_cert_file or not body.tls_key_file):
        raise HTTPException(status_code=400, detail="HTTPS requires certificate and key file paths")
    row = await db.get(SystemSetting, _SECURITY_KEY)
    if row is None:
        row = SystemSetting(key=_SECURITY_KEY, value=body.model_dump())
        db.add(row)
    else:
        row.value = body.model_dump()
    audit("settings.security.update", target="security", settings=body.model_dump())
    return body


@router.get("/users", response_model=list[UserRead])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[UserRead]:
    result = await db.execute(select(AppUser).order_by(AppUser.username))
    return [UserRead.model_validate(user) for user in result.scalars().all()]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    existing = await db.execute(select(AppUser).where(AppUser.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AppUser(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password.get_secret_value()),
        role=body.role,
        user_type=body.user_type,
        virtual_domain=body.virtual_domain,
        enabled=body.enabled,
        force_password_change=body.force_password_change,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    audit("user.create", target=str(user.id), username=user.username, role=user.role, user_type=user.user_type)
    return UserRead.model_validate(user)


@router.patch("/users/{id}", response_model=UserRead)
async def update_user(id: uuid.UUID, body: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = body.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in data.items():
        setattr(user, field, value)
    if body.password is not None:
        user.password_hash = hash_password(body.password.get_secret_value())
    await db.flush()
    await db.refresh(user)
    audit("user.update", target=str(user.id), username=user.username, role=user.role, user_type=user.user_type)
    return UserRead.model_validate(user)


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    audit("user.delete", target=str(id), username=user.username)
