"""System settings and local user administration."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.permissions_catalog import (
    BUILT_IN_ROLES,
    PERMISSION_CATALOG,
    PERMISSION_DESCRIPTIONS,
    SYSTEM_SETTINGS_SUBMENUS,
    all_permission_keys,
)
from app.config import settings
from app.database import get_db
from app.models.system import AppRole, AppUser, SystemSetting
from app.security.audit import audit
from app.security.passwords import hash_password

router = APIRouter()
_SECURITY_KEY = "security"
_SYSTEM_KEY = "system"
_NETWORK_DEVICES_KEY = "network_devices"
_ALARMS_EVENTS_KEY = "alarms_events"
_PROFILE_VERSION = 1

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# ---------------------------------------------------------------------------
# System settings: mail / jobs / retention
# ---------------------------------------------------------------------------

class SystemMailSettings(BaseModel):
    smtp_host: str = Field("", max_length=255)
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_from: str = Field("", max_length=255)
    smtp_use_tls: bool = True
    smtp_username: str = Field("", max_length=255)

    @field_validator("smtp_from")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if value and not _EMAIL_PATTERN.match(value):
            raise ValueError("smtp_from must be a valid email address")
        return value


class SystemJobSettings(BaseModel):
    job_concurrency: int = Field(4, ge=1, le=64)
    job_retry_backoff_seconds: int = Field(30, ge=5, le=3600)
    job_max_retries: int = Field(3, ge=0, le=20)


class SystemRetentionSettings(BaseModel):
    alarm_retention_days: int = Field(90, ge=1, le=3650)
    event_retention_days: int = Field(30, ge=1, le=3650)
    kpi_retention_days: int = Field(365, ge=1, le=3650)
    telemetry_sample_retention_days: int = Field(7, ge=1, le=365)


class SystemAdminSettings(BaseModel):
    mail: SystemMailSettings = Field(default_factory=SystemMailSettings)
    jobs: SystemJobSettings = Field(default_factory=SystemJobSettings)
    retention: SystemRetentionSettings = Field(default_factory=SystemRetentionSettings)


# ---------------------------------------------------------------------------
# Network device settings: CLI / SNMP defaults
# ---------------------------------------------------------------------------

class NetworkCliSettings(BaseModel):
    ssh_timeout_seconds: int = Field(30, ge=1, le=600)
    ssh_port: int = Field(22, ge=1, le=65535)
    cli_retries: int = Field(2, ge=0, le=10)
    max_concurrent_ssh_sessions: int = Field(10, ge=1, le=200)
    terminal_length: int = Field(0, ge=0, le=512)


class NetworkSnmpSettings(BaseModel):
    snmp_version: Literal["v2c", "v3"] = "v2c"
    snmp_community: str = Field("public", max_length=255)
    snmp_port: int = Field(161, ge=1, le=65535)
    snmp_timeout_seconds: int = Field(5, ge=1, le=120)
    snmp_retries: int = Field(2, ge=0, le=10)
    polling_interval_seconds: int = Field(60, ge=10, le=86400)


class NetworkDeviceAdminSettings(BaseModel):
    cli: NetworkCliSettings = Field(default_factory=NetworkCliSettings)
    snmp: NetworkSnmpSettings = Field(default_factory=NetworkSnmpSettings)


# ---------------------------------------------------------------------------
# Alarms/Events settings: severity / notifications
# ---------------------------------------------------------------------------

class AlarmSeverityMapping(BaseModel):
    critical_oid_value: int = Field(1, ge=0)
    major_oid_value: int = Field(2, ge=0)
    minor_oid_value: int = Field(3, ge=0)
    warning_oid_value: int = Field(4, ge=0)
    info_oid_value: int = Field(5, ge=0)


class AlarmNotificationSettings(BaseModel):
    email_enabled: bool = False
    email_recipients: str = Field("", max_length=2048)
    syslog_forward_enabled: bool = False
    syslog_forward_host: str = Field("", max_length=255)
    syslog_forward_port: int = Field(514, ge=1, le=65535)
    min_severity_to_notify: Literal["critical", "major", "minor", "warning", "info"] = "major"

    @field_validator("syslog_forward_host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        if value and (".." in value or any(ch in value for ch in "\r\n\x00 ")):
            raise ValueError("Invalid syslog host")
        return value


class AlarmSuppressionSettings(BaseModel):
    suppression_window_minutes: int = Field(5, ge=0, le=1440)
    flap_detection_enabled: bool = True
    flap_threshold_count: int = Field(3, ge=1, le=100)


class AlarmsEventsAdminSettings(BaseModel):
    severity_mapping: AlarmSeverityMapping = Field(default_factory=AlarmSeverityMapping)
    notifications: AlarmNotificationSettings = Field(default_factory=AlarmNotificationSettings)
    suppression: AlarmSuppressionSettings = Field(default_factory=AlarmSuppressionSettings)


# ---------------------------------------------------------------------------
# Generic DB load/save helpers
# ---------------------------------------------------------------------------

async def _load_setting(db: AsyncSession, key: str, model_cls: type, defaults_fn) -> BaseModel:
    row = await db.get(SystemSetting, key)
    if not row:
        return defaults_fn()
    return model_cls(**{**defaults_fn().model_dump(), **row.value})


async def _save_setting(db: AsyncSession, key: str, data: BaseModel) -> None:
    row = await db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key, value=data.model_dump())
        db.add(row)
    else:
        row.value = data.model_dump()


async def _load_security_settings(db: AsyncSession) -> SecuritySettings:
    row = await db.get(SystemSetting, _SECURITY_KEY)
    if not row:
        return _defaults()
    return SecuritySettings(**{**_defaults().model_dump(), **row.value})


# ---------------------------------------------------------------------------
# System settings endpoints
# ---------------------------------------------------------------------------

@router.get("/system", response_model=SystemAdminSettings)
async def get_system_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> SystemAdminSettings:
    return await _load_setting(db, _SYSTEM_KEY, SystemAdminSettings, SystemAdminSettings)


@router.put("/system", response_model=SystemAdminSettings)
async def update_system_settings(
    body: SystemAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SystemAdminSettings:
    await _save_setting(db, _SYSTEM_KEY, body)
    audit("settings.system.update", target=_SYSTEM_KEY)
    return body


# ---------------------------------------------------------------------------
# Network device settings endpoints
# ---------------------------------------------------------------------------

@router.get("/network-devices", response_model=NetworkDeviceAdminSettings)
async def get_network_device_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> NetworkDeviceAdminSettings:
    return await _load_setting(db, _NETWORK_DEVICES_KEY, NetworkDeviceAdminSettings, NetworkDeviceAdminSettings)


@router.put("/network-devices", response_model=NetworkDeviceAdminSettings)
async def update_network_device_settings(
    body: NetworkDeviceAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NetworkDeviceAdminSettings:
    await _save_setting(db, _NETWORK_DEVICES_KEY, body)
    audit("settings.network_devices.update", target=_NETWORK_DEVICES_KEY)
    return body


# ---------------------------------------------------------------------------
# Alarms/Events settings endpoints
# ---------------------------------------------------------------------------

@router.get("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def get_alarms_events_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> AlarmsEventsAdminSettings:
    return await _load_setting(db, _ALARMS_EVENTS_KEY, AlarmsEventsAdminSettings, AlarmsEventsAdminSettings)


@router.put("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def update_alarms_events_settings(
    body: AlarmsEventsAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AlarmsEventsAdminSettings:
    await _save_setting(db, _ALARMS_EVENTS_KEY, body)
    audit("settings.alarms_events.update", target=_ALARMS_EVENTS_KEY)
    return body

def _validate_permissions(values: dict[str, bool]) -> dict[str, bool]:
    allowed = all_permission_keys()
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
    return values


def _validate_password_strength(password: SecretStr, username: str | None = None, display_name: str | None = None) -> SecretStr:
    value = password.get_secret_value()
    if len(value) < 12:
        raise ValueError("Password must be at least 12 characters")
    if not any(ch.isupper() for ch in value):
        raise ValueError("Password must include at least one uppercase letter")
    if not any(ch.islower() for ch in value):
        raise ValueError("Password must include at least one lowercase letter")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("Password must include at least one number")
    if not any(not ch.isalnum() and not ch.isspace() for ch in value):
        raise ValueError("Password must include at least one special character")
    if any(ch.isspace() for ch in value):
        raise ValueError("Password must not contain spaces or line breaks")

    lowered = value.lower()
    identity_parts = [username or ""]
    if display_name:
        identity_parts.extend(display_name.split())
    for part in identity_parts:
        normalized = part.strip().lower()
        if len(normalized) >= 3 and normalized in lowered:
            raise ValueError("Password must not contain username or display name fragments")
    return password


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


class SettingsProfile(BaseModel):
    profile_version: int = _PROFILE_VERSION
    security: SecuritySettings
    system: SystemAdminSettings
    network_devices: NetworkDeviceAdminSettings
    alarms_events: AlarmsEventsAdminSettings


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    display_name: str | None = None
    role: str
    roles: list[str] = Field(default_factory=list)
    user_type: str
    custom_permissions: dict[str, bool] = Field(default_factory=dict)
    virtual_domain: str | None = None
    enabled: bool
    force_password_change: bool


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, pattern=r"^[A-Za-z0-9_.@-]+$")
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr = Field(..., min_length=12)
    role: str = Field("admin", max_length=255)
    roles: list[str] = Field(default_factory=list, max_length=20)
    user_type: Literal["web", "nbi"] = "web"
    custom_permissions: dict[str, bool] = Field(default_factory=dict)
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool = True
    force_password_change: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        return _validate_password_strength(value, info.data.get("username"), info.data.get("display_name"))

    @field_validator("custom_permissions")
    @classmethod
    def validate_custom_permissions(cls, value: dict[str, bool]) -> dict[str, bool]:
        return _validate_permissions(value)

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str]) -> list[str]:
        return [role for role in value if role]


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr | None = Field(None, min_length=12)
    role: str | None = Field(None, max_length=255)
    roles: list[str] | None = Field(None, max_length=20)
    user_type: Literal["web", "nbi"] | None = None
    custom_permissions: dict[str, bool] | None = None
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    force_password_change: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: SecretStr | None, info: ValidationInfo) -> SecretStr | None:
        if value is None:
            return None
        return _validate_password_strength(value, info.data.get("username"), info.data.get("display_name"))

    @field_validator("custom_permissions")
    @classmethod
    def validate_custom_permissions(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        return _validate_permissions(value) if value is not None else None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, value: list[str] | None) -> list[str] | None:
        return [role for role in value if role] if value is not None else None


class RoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    display_name: str | None = None
    description: str | None = None
    user_type: str
    permissions: dict[str, bool]
    built_in: bool
    editable: bool = True

    @classmethod
    def from_role(cls, role: AppRole) -> "RoleRead":
        meta = BUILT_IN_ROLES.get(role.name, {})
        return cls(
            id=role.id,
            name=role.name,
            display_name=meta.get("display_name") or role.name.replace("_", " ").title(),
            description=role.description,
            user_type=role.user_type,
            permissions=role.permissions or {},
            built_in=role.built_in,
            editable=bool(meta.get("editable", True)) if role.built_in else True,
        )


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.@-]+$")
    description: str | None = Field(None, max_length=255)
    user_type: Literal["web", "nbi"] = "web"
    permissions: dict[str, bool] = Field(default_factory=dict)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, bool]) -> dict[str, bool]:
        return _validate_permissions(value)


class RoleUpdate(BaseModel):
    description: str | None = Field(None, max_length=255)
    user_type: Literal["web", "nbi"] | None = None
    permissions: dict[str, bool] | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        return _validate_permissions(value) if value is not None else None


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


async def _ensure_builtin_roles(db: AsyncSession) -> None:
    for name, spec in BUILT_IN_ROLES.items():
        result = await db.execute(select(AppRole).where(AppRole.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            db.add(AppRole(name=name, description=spec["description"], user_type=spec["user_type"], permissions=spec["permissions"], built_in=True))
        else:
            role.description = spec["description"]
            role.user_type = spec["user_type"]
            # Preserve customized permissions for editable built-ins; reset locked ones.
            if not spec.get("editable", True) or not role.permissions:
                role.permissions = spec["permissions"]
            role.built_in = True
    # Flush so the SELECT below sees the newly added rows in the same transaction.
    await db.flush()


@router.get("/security", response_model=SecuritySettings)
async def get_security_settings(db: Annotated[AsyncSession, Depends(get_db)]) -> SecuritySettings:
    return await _load_security_settings(db)


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


@router.get("/profile", response_model=SettingsProfile)
async def export_settings_profile(db: Annotated[AsyncSession, Depends(get_db)]) -> SettingsProfile:
    profile = SettingsProfile(
        security=await _load_security_settings(db),
        system=await _load_setting(db, _SYSTEM_KEY, SystemAdminSettings, SystemAdminSettings),
        network_devices=await _load_setting(
            db,
            _NETWORK_DEVICES_KEY,
            NetworkDeviceAdminSettings,
            NetworkDeviceAdminSettings,
        ),
        alarms_events=await _load_setting(
            db,
            _ALARMS_EVENTS_KEY,
            AlarmsEventsAdminSettings,
            AlarmsEventsAdminSettings,
        ),
    )
    audit("settings.profile.export", target="settings-profile")
    return profile


@router.put("/profile", response_model=SettingsProfile)
async def import_settings_profile(
    body: SettingsProfile,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SettingsProfile:
    if body.profile_version != _PROFILE_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported settings profile version {body.profile_version}",
        )
    if body.security.https_enabled and (
        not body.security.tls_cert_file or not body.security.tls_key_file
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HTTPS requires certificate and key file paths",
        )

    await _save_setting(db, _SECURITY_KEY, body.security)
    await _save_setting(db, _SYSTEM_KEY, body.system)
    await _save_setting(db, _NETWORK_DEVICES_KEY, body.network_devices)
    await _save_setting(db, _ALARMS_EVENTS_KEY, body.alarms_events)
    audit(
        "settings.profile.import",
        target="settings-profile",
        profile_version=body.profile_version,
    )
    return body


@router.get("/users", response_model=list[UserRead])
async def list_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[UserRead]:
    result = await db.execute(select(AppUser).order_by(AppUser.username))
    return [UserRead.model_validate(user) for user in result.scalars().all()]


@router.get("/permissions")
async def list_permission_catalog() -> dict[str, list[dict[str, str]]]:
    return PERMISSION_CATALOG


@router.get("/permissions/descriptions")
async def list_permission_descriptions() -> dict[str, str]:
    return PERMISSION_DESCRIPTIONS


@router.get("/permissions/system-settings")
async def list_system_settings_permissions() -> list[dict[str, str]]:
    """Table 2: Additional Permissions for System Settings Submenus (EPNM 4.0)."""
    return SYSTEM_SETTINGS_SUBMENUS


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(db: Annotated[AsyncSession, Depends(get_db)]) -> list[RoleRead]:
    await _ensure_builtin_roles(db)
    result = await db.execute(select(AppRole).order_by(AppRole.built_in.desc(), AppRole.name))
    return [RoleRead.from_role(role) for role in result.scalars().all()]


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(body: RoleCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> RoleRead:
    existing = await db.execute(select(AppRole).where(AppRole.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Role already exists")
    role = AppRole(**body.model_dump(), built_in=False)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    audit("role.create", target=str(role.id), name=role.name, user_type=role.user_type, permissions=role.permissions)
    return RoleRead.from_role(role)


@router.patch("/roles/{id}", response_model=RoleRead)
async def update_role(id: uuid.UUID, body: RoleUpdate, db: Annotated[AsyncSession, Depends(get_db)]) -> RoleRead:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        meta = BUILT_IN_ROLES.get(role.name, {})
        if meta.get("editable", True) is False:
            raise HTTPException(status_code=400, detail="This built-in role is locked and cannot be modified")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.flush()
    await db.refresh(role)
    audit("role.update", target=str(role.id), name=role.name, user_type=role.user_type, permissions=role.permissions)
    return RoleRead.from_role(role)


@router.delete("/roles/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]) -> None:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        raise HTTPException(status_code=400, detail="Built-in roles cannot be deleted")
    await db.delete(role)
    audit("role.delete", target=str(id), name=role.name)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]) -> UserRead:
    existing = await db.execute(select(AppUser).where(AppUser.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AppUser(
        username=body.username,
        display_name=body.display_name,
        password_hash=hash_password(body.password.get_secret_value()),
        role=",".join(body.roles) if body.roles else body.role,
        user_type=body.user_type,
        custom_permissions=body.custom_permissions,
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
    data = body.model_dump(exclude_unset=True, exclude={"password", "roles"})
    for field, value in data.items():
        setattr(user, field, value)
    if body.roles is not None:
        user.role = ",".join(body.roles)
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
