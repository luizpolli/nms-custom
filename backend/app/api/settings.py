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
from app.models.system import AppRole, AppUser, SystemSetting
from app.security.audit import audit
from app.security.passwords import hash_password

router = APIRouter()
_SECURITY_KEY = "security"

PERMISSION_CATALOG: dict[str, list[dict[str, str]]] = {
    "Monitor": [
        {"key": "dashboard.view", "label": "View dashboards"},
        {"key": "alarms.view", "label": "View alarms and events"},
        {"key": "reports.view", "label": "View reports"},
    ],
    "Devices": [
        {"key": "devices.view", "label": "View devices"},
        {"key": "devices.manage", "label": "Add/edit/delete devices"},
        {"key": "devices.credentials.assign", "label": "Assign device credentials"},
        {"key": "discovery.run", "label": "Run discovery"},
        {"key": "topology.manage", "label": "Build/manage topology"},
    ],
    "Configuration": [
        {"key": "commands.view", "label": "View command templates"},
        {"key": "commands.run", "label": "Run commands/jobs"},
        {"key": "commands.approve", "label": "Approve jobs"},
        {"key": "inventory.manage", "label": "Manage inventory/images"},
    ],
    "Administration": [
        {"key": "credentials.manage", "label": "Manage credentials"},
        {"key": "users.manage", "label": "Manage users and roles"},
        {"key": "settings.manage", "label": "System Settings"},
        {"key": "audit.view", "label": "View audit trail"},
    ],
    "Notification Policies": [
        {"key": "notification_policies.read", "label": "Notification Policies Read Access"},
        {"key": "notification_policies.write", "label": "Notification Policies Read-Write Access"},
    ],
    "Network Topology": [
        {"key": "network_topology", "label": "Network Topology"},
        {"key": "circuit_vc.monitor", "label": "Circuit or VC Monitoring and Troubleshooting"},
    ],
    "Performance": [
        {"key": "performance_dashboard", "label": "Performance Dashboard"},
    ],
    "NBI": [
        {"key": "nbi.read", "label": "NBI read access"},
        {"key": "nbi.write", "label": "NBI write access"},
    ],
}

SYSTEM_SETTINGS_SUBMENU_PERMISSIONS: list[dict[str, str]] = [
    {"task_group": "General", "task_name": "Account Settings", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Data Retention", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Job Approval", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Login Disclaimer", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Report", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Server", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "Software Update", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "General", "task_name": "User Defined Fields", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Mail & Notification", "task_name": "Change Audit Notification", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Mail & Notification", "task_name": "Mail Server Configuration", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Mail & Notification", "task_name": "Notification Destination", "additional_permission": "Notification Policies Read Access or Notification Policies Read-Write Access", "permission_key": "notification_policies.read"},
    {"task_group": "Network and Device", "task_name": "SNMP", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "Configuration", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "Configuration Archive", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "Network Discovery", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "Software Image Management", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "Inventory", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Inventory", "task_name": "SRRG Pool Types", "additional_permission": "Network Topology", "permission_key": "network_topology"},
    {"task_group": "Inventory", "task_name": "SRRG Pool", "additional_permission": "Network Topology", "permission_key": "network_topology"},
    {"task_group": "Inventory", "task_name": "Sync Offline Devices", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Maps", "task_name": "Network Topology", "additional_permission": "Network Topology", "permission_key": "network_topology"},
    {"task_group": "Maps", "task_name": "Bandwidth Utilization", "additional_permission": "Network Topology", "permission_key": "network_topology"},
    {"task_group": "Circuit VCs", "task_name": "Discovery settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting", "permission_key": "circuit_vc.monitor"},
    {"task_group": "Circuit VCs", "task_name": "Circuits VCs Display", "additional_permission": "Circuit or VC Monitoring and Troubleshooting", "permission_key": "circuit_vc.monitor"},
    {"task_group": "Circuit VCs", "task_name": "Archive Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting", "permission_key": "circuit_vc.monitor"},
    {"task_group": "Circuit VCs", "task_name": "Deployment Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting", "permission_key": "circuit_vc.monitor"},
    {"task_group": "Circuit VCs", "task_name": "WAE Server Settings", "additional_permission": "Circuit or VC Monitoring and Troubleshooting", "permission_key": "circuit_vc.monitor"},
    {"task_group": "Alarm and Events", "task_name": "Alarm and Events", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Alarm and Events", "task_name": "Alarm Severity and autoclear", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Alarm and Events", "task_name": "System Event Configuration", "additional_permission": "System Settings", "permission_key": "settings.manage"},
    {"task_group": "Alarm and Events", "task_name": "Alarm Notification Policies", "additional_permission": "Notification Policies Read Access or Notification Policies Read-Write Access", "permission_key": "notification_policies.read"},
    {"task_group": "Performance", "task_name": "PTP/SyncE", "additional_permission": "Performance Dashboard", "permission_key": "performance_dashboard"},
]


BUILT_IN_ROLES: dict[str, dict] = {
    "admin": {"description": "Full web GUI administration", "user_type": "web", "permissions": {"*": True}},
    "super_user": {"description": "Full operations except root-only bootstrap", "user_type": "web", "permissions": {"*": True, "root.manage": False}},
    "config_manager": {"description": "Device, discovery, topology and command configuration", "user_type": "web", "permissions": {"devices.view": True, "devices.manage": True, "discovery.run": True, "topology.manage": True, "commands.view": True, "commands.run": True, "reports.view": True}},
    "operator": {"description": "Operate and monitor managed devices", "user_type": "web", "permissions": {"dashboard.view": True, "alarms.view": True, "devices.view": True, "commands.run": True, "reports.view": True}},
    "viewer": {"description": "Read-only web GUI access", "user_type": "web", "permissions": {"dashboard.view": True, "alarms.view": True, "devices.view": True, "reports.view": True}},
    "nbi_read": {"description": "Read-only NBI REST API access", "user_type": "nbi", "permissions": {"nbi.read": True}},
    "nbi_write": {"description": "Read/write NBI REST API access", "user_type": "nbi", "permissions": {"nbi.read": True, "nbi.write": True}},
}


def _validate_permissions(values: dict[str, bool]) -> dict[str, bool]:
    allowed = {"*", "root.manage"}
    for group in PERMISSION_CATALOG.values():
        allowed.update(item["key"] for item in group)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
    return values


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
    custom_permissions: dict[str, bool] = Field(default_factory=dict)
    virtual_domain: str | None = None
    enabled: bool
    force_password_change: bool


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255, pattern=r"^[A-Za-z0-9_.@-]+$")
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr = Field(..., min_length=12)
    role: str = Field("viewer", max_length=100)
    user_type: Literal["web", "nbi"] = "web"
    custom_permissions: dict[str, bool] = Field(default_factory=dict)
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool = True
    force_password_change: bool = False

    @field_validator("custom_permissions")
    @classmethod
    def validate_custom_permissions(cls, value: dict[str, bool]) -> dict[str, bool]:
        return _validate_permissions(value)


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=255)
    password: SecretStr | None = Field(None, min_length=12)
    role: str | None = Field(None, max_length=100)
    user_type: Literal["web", "nbi"] | None = None
    custom_permissions: dict[str, bool] | None = None
    virtual_domain: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    force_password_change: bool | None = None

    @field_validator("custom_permissions")
    @classmethod
    def validate_custom_permissions(cls, value: dict[str, bool] | None) -> dict[str, bool] | None:
        return _validate_permissions(value) if value is not None else None


class RoleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    description: str | None = None
    user_type: str
    permissions: dict[str, bool]
    built_in: bool


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
            role.permissions = spec["permissions"]
            role.built_in = True


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


@router.get("/permissions")
async def list_permission_catalog() -> dict[str, list[dict[str, str]]]:
    return PERMISSION_CATALOG


@router.get("/permissions/system-settings")
async def list_system_settings_permissions() -> list[dict[str, str]]:
    """Table 2: Additional Permissions for System Settings Submenus (EPNM 4.0)."""
    return SYSTEM_SETTINGS_SUBMENU_PERMISSIONS


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(db: Annotated[AsyncSession, Depends(get_db)]) -> list[RoleRead]:
    await _ensure_builtin_roles(db)
    result = await db.execute(select(AppRole).order_by(AppRole.built_in.desc(), AppRole.name))
    return [RoleRead.model_validate(role) for role in result.scalars().all()]


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
    return RoleRead.model_validate(role)


@router.patch("/roles/{id}", response_model=RoleRead)
async def update_role(id: uuid.UUID, body: RoleUpdate, db: Annotated[AsyncSession, Depends(get_db)]) -> RoleRead:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        raise HTTPException(status_code=400, detail="Built-in roles cannot be modified; clone into a custom role")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    await db.flush()
    await db.refresh(role)
    audit("role.update", target=str(role.id), name=role.name, user_type=role.user_type, permissions=role.permissions)
    return RoleRead.model_validate(role)


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
        role=body.role,
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
