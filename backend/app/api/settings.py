"""System settings and local user administration."""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator
from sqlalchemy import or_, select
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
from app.models.audit import AuditLog
from app.models.system import AppRole, AppUser, SystemSetting
from app.schemas.audit import AuditLogRead
from app.security.audit import audit
from app.security.auth import (
    PERM_SETTINGS_ALARMS_EVENTS,
    PERM_SETTINGS_AUDIT_TRAILS,
    PERM_SETTINGS_NETWORK_SNMP,
    PERM_SETTINGS_SYSTEM,
    PERM_SETTINGS_USER_ADMIN_USERS_GROUPS,
    PERM_SETTINGS_USERS_GROUPS,
    PERM_SETTINGS_VIEW_AUDIT,
    Principal,
    require_settings_permission,
)
from app.security.passwords import hash_password
from app.services.account_audit import ACCOUNT_AUDIT_OBJECT_TYPE, record_account_activity

_S = TypeVar("_S", bound=BaseModel)

router = APIRouter()
_SECURITY_KEY = "security"
_GENERAL_KEY = "general"
_SYSTEM_KEY = "system"
_NETWORK_DEVICES_KEY = "network_devices"
_INVENTORY_KEY = "inventory"
_ALARMS_EVENTS_KEY = "alarms_events"
_INTEGRATIONS_AI_OPS_KEY = "integrations_ai_ops"
_LAB_OPERATIONS_KEY = "lab_operations"
_MODULES_KEY = "modules"
_PROFILE_VERSION = 3

_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _record_settings_audit(
    db: AsyncSession,
    action: str,
    *,
    target: str,
    details: dict | None = None,
) -> None:
    audit(action, target=target, **(details or {}))
    db.add(
        AuditLog(
            actor="system",
            action=action,
            object_type="settings",
            object_id=target,
            outcome="success",
            details=details or {},
        )
    )


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
    mail: SystemMailSettings = Field(default_factory=SystemMailSettings)  # type: ignore[arg-type]
    jobs: SystemJobSettings = Field(default_factory=SystemJobSettings)  # type: ignore[arg-type]
    retention: SystemRetentionSettings = Field(default_factory=SystemRetentionSettings)  # type: ignore[arg-type]


class SettingsTestResult(BaseModel):
    ok: bool
    message: str
    checks: list[str] = Field(default_factory=list)


def _test_mail_settings(mail: SystemMailSettings) -> SettingsTestResult:
    checks = [
        f"SMTP endpoint parsed: {mail.smtp_host or 'not configured'}:{mail.smtp_port}",
        f"TLS enabled: {'yes' if mail.smtp_use_tls else 'no'}",
    ]
    if mail.smtp_host and not mail.smtp_from:
        return SettingsTestResult(
            ok=False,
            message="SMTP host is configured but the From address is empty.",
            checks=checks,
        )
    return SettingsTestResult(
        ok=True,
        message="Mail notification configuration passed validation. No external SMTP delivery was attempted.",
        checks=checks,
    )


# ---------------------------------------------------------------------------
# General settings: product identity / support links
# ---------------------------------------------------------------------------

class GeneralAdminSettings(BaseModel):
    product_name: str = Field("NMS Custom", min_length=1, max_length=120)
    deployment_name: str = Field("Lab", max_length=120)
    default_theme: Literal["system", "light", "dark"] = "system"
    support_contact_name: str = Field("", max_length=120)
    support_contact_email: str = Field("", max_length=255)
    tac_case_url: str = Field("", max_length=512)
    cisco_account_name: str = Field("", max_length=120)

    @field_validator("support_contact_email")
    @classmethod
    def validate_support_email(cls, value: str) -> str:
        if value and not _EMAIL_PATTERN.match(value):
            raise ValueError("support_contact_email must be a valid email address")
        return value

    @field_validator("tac_case_url")
    @classmethod
    def validate_tac_url(cls, value: str) -> str:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("tac_case_url must be an HTTP(S) URL")
        return value


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
    cli: NetworkCliSettings = Field(default_factory=NetworkCliSettings)  # type: ignore[arg-type]
    snmp: NetworkSnmpSettings = Field(default_factory=NetworkSnmpSettings)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Inventory settings: archives / discovery / lifecycle
# ---------------------------------------------------------------------------

class InventoryAdminSettings(BaseModel):
    config_archive_enabled: bool = True
    config_archive_frequency_minutes: int = Field(1440, ge=15, le=10080)
    config_archive_retention_days: int = Field(90, ge=1, le=3650)
    image_repository_path: str = Field("", max_length=512)
    default_discovery_profile: str = Field("snmp-cli", max_length=120)
    auto_group_by_site: bool = True
    lifecycle_warning_days: int = Field(180, ge=1, le=3650)

    @field_validator("image_repository_path")
    @classmethod
    def validate_repository_path(cls, value: str) -> str:
        if value and any(ch in value for ch in "\r\n\x00"):
            raise ValueError("Invalid image repository path")
        return value


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
    severity_mapping: AlarmSeverityMapping = Field(default_factory=AlarmSeverityMapping)  # type: ignore[arg-type]
    notifications: AlarmNotificationSettings = Field(default_factory=AlarmNotificationSettings)  # type: ignore[arg-type]
    suppression: AlarmSuppressionSettings = Field(default_factory=AlarmSuppressionSettings)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integrations / AI Ops settings
# ---------------------------------------------------------------------------

class IntegrationsAiOpsAdminSettings(BaseModel):
    nbi_enabled: bool = True
    webhook_retry_attempts: int = Field(3, ge=0, le=20)
    webhook_timeout_seconds: int = Field(10, ge=1, le=300)
    ai_ops_enabled: bool = True
    ai_recommendation_min_confidence: int = Field(70, ge=0, le=100)
    llm_provider: Literal["local", "openai", "azure", "custom"] = "local"
    llm_model: str = Field("", max_length=120)
    report_export_target_path: str = Field("", max_length=512)

    @field_validator("report_export_target_path")
    @classmethod
    def validate_export_path(cls, value: str) -> str:
        if value and any(ch in value for ch in "\r\n\x00"):
            raise ValueError("Invalid export target path")
        return value


# ---------------------------------------------------------------------------
# Lab / Operations settings
# ---------------------------------------------------------------------------

class LabOperationsAdminSettings(BaseModel):
    certification_mode_enabled: bool = True
    traffic_simulator_enabled: bool = False
    simulator_profile: str = Field("baseline", max_length=120)
    maintenance_mode_enabled: bool = False
    maintenance_window: str = Field("", max_length=255)
    runbook_url: str = Field("", max_length=512)
    ptp_synce_enabled: bool = False

    @field_validator("runbook_url")
    @classmethod
    def validate_runbook_url(cls, value: str) -> str:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("runbook_url must be an HTTP(S) URL")
        return value


# ---------------------------------------------------------------------------
# Module control settings
# ---------------------------------------------------------------------------

class ModuleControlSettings(BaseModel):
    dashboard: bool = True
    devices: bool = True
    inventory: bool = True
    credentials: bool = True
    performance: bool = True
    telemetry: bool = True
    alarms: bool = True
    assurance: bool = True
    services: bool = True
    ai_ops: bool = True
    monitoring_policies: bool = True
    topology: bool = True
    discovery: bool = True
    commands: bool = True
    ios: bool = True
    reports: bool = True


# ---------------------------------------------------------------------------
# Generic DB load/save helpers
# ---------------------------------------------------------------------------

async def _load_setting(
    db: AsyncSession,
    key: str,
    model_cls: type[_S],
    defaults_fn: type[_S] | Callable[[], _S],
) -> _S:
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
# General settings endpoints
# ---------------------------------------------------------------------------

@router.get("/general", response_model=GeneralAdminSettings)
async def get_general_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> GeneralAdminSettings:
    return await _load_setting(db, _GENERAL_KEY, GeneralAdminSettings, GeneralAdminSettings)


@router.put("/general", response_model=GeneralAdminSettings)
async def update_general_settings(
    body: GeneralAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> GeneralAdminSettings:
    await _save_setting(db, _GENERAL_KEY, body)
    _record_settings_audit(db, "settings.general.update", target=_GENERAL_KEY)
    return body


# ---------------------------------------------------------------------------
# System settings endpoints
# ---------------------------------------------------------------------------

@router.get("/system", response_model=SystemAdminSettings)
async def get_system_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SystemAdminSettings:
    return await _load_setting(db, _SYSTEM_KEY, SystemAdminSettings, SystemAdminSettings)


@router.put("/system", response_model=SystemAdminSettings)
async def update_system_settings(
    body: SystemAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SystemAdminSettings:
    await _save_setting(db, _SYSTEM_KEY, body)
    _record_settings_audit(db, "settings.system.update", target=_SYSTEM_KEY)
    return body


@router.post("/mail/test", response_model=SettingsTestResult)
async def test_mail_settings(
    body: SystemMailSettings,
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SettingsTestResult:
    return _test_mail_settings(body)


@router.post("/system/test", response_model=SettingsTestResult)
async def test_system_settings(
    body: SystemAdminSettings,
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SettingsTestResult:
    return _test_mail_settings(body.mail)


# ---------------------------------------------------------------------------
# Network device settings endpoints
# ---------------------------------------------------------------------------

@router.get("/network-devices", response_model=NetworkDeviceAdminSettings)
async def get_network_device_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_NETWORK_SNMP))],
) -> NetworkDeviceAdminSettings:
    return await _load_setting(db, _NETWORK_DEVICES_KEY, NetworkDeviceAdminSettings, NetworkDeviceAdminSettings)


@router.put("/network-devices", response_model=NetworkDeviceAdminSettings)
async def update_network_device_settings(
    body: NetworkDeviceAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_NETWORK_SNMP))],
) -> NetworkDeviceAdminSettings:
    await _save_setting(db, _NETWORK_DEVICES_KEY, body)
    _record_settings_audit(db, "settings.network_devices.update", target=_NETWORK_DEVICES_KEY)
    return body


# ---------------------------------------------------------------------------
# Inventory settings endpoints
# ---------------------------------------------------------------------------

@router.get("/inventory", response_model=InventoryAdminSettings)
async def get_inventory_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> InventoryAdminSettings:
    return await _load_setting(db, _INVENTORY_KEY, InventoryAdminSettings, InventoryAdminSettings)


@router.put("/inventory", response_model=InventoryAdminSettings)
async def update_inventory_settings(
    body: InventoryAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> InventoryAdminSettings:
    await _save_setting(db, _INVENTORY_KEY, body)
    _record_settings_audit(db, "settings.inventory.update", target=_INVENTORY_KEY)
    return body


# ---------------------------------------------------------------------------
# Alarms/Events settings endpoints
# ---------------------------------------------------------------------------

@router.get("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def get_alarms_events_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_ALARMS_EVENTS))],
) -> AlarmsEventsAdminSettings:
    return await _load_setting(db, _ALARMS_EVENTS_KEY, AlarmsEventsAdminSettings, AlarmsEventsAdminSettings)


@router.put("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def update_alarms_events_settings(
    body: AlarmsEventsAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_ALARMS_EVENTS))],
) -> AlarmsEventsAdminSettings:
    await _save_setting(db, _ALARMS_EVENTS_KEY, body)
    _record_settings_audit(db, "settings.alarms_events.update", target=_ALARMS_EVENTS_KEY)
    return body


# ---------------------------------------------------------------------------
# Integrations / AI Ops settings endpoints
# ---------------------------------------------------------------------------

@router.get("/integrations-ai-ops", response_model=IntegrationsAiOpsAdminSettings)
async def get_integrations_ai_ops_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> IntegrationsAiOpsAdminSettings:
    return await _load_setting(
        db,
        _INTEGRATIONS_AI_OPS_KEY,
        IntegrationsAiOpsAdminSettings,
        IntegrationsAiOpsAdminSettings,
    )


@router.put("/integrations-ai-ops", response_model=IntegrationsAiOpsAdminSettings)
async def update_integrations_ai_ops_settings(
    body: IntegrationsAiOpsAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> IntegrationsAiOpsAdminSettings:
    await _save_setting(db, _INTEGRATIONS_AI_OPS_KEY, body)
    _record_settings_audit(db, "settings.integrations_ai_ops.update", target=_INTEGRATIONS_AI_OPS_KEY)
    return body


# ---------------------------------------------------------------------------
# Lab / Operations settings endpoints
# ---------------------------------------------------------------------------

@router.get("/lab-operations", response_model=LabOperationsAdminSettings)
async def get_lab_operations_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> LabOperationsAdminSettings:
    return await _load_setting(
        db,
        _LAB_OPERATIONS_KEY,
        LabOperationsAdminSettings,
        LabOperationsAdminSettings,
    )


@router.put("/lab-operations", response_model=LabOperationsAdminSettings)
async def update_lab_operations_settings(
    body: LabOperationsAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> LabOperationsAdminSettings:
    await _save_setting(db, _LAB_OPERATIONS_KEY, body)
    _record_settings_audit(db, "settings.lab_operations.update", target=_LAB_OPERATIONS_KEY)
    return body


# ---------------------------------------------------------------------------
# Module control settings endpoints
# ---------------------------------------------------------------------------

@router.get("/modules", response_model=ModuleControlSettings)
async def get_module_control_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> ModuleControlSettings:
    return await _load_setting(db, _MODULES_KEY, ModuleControlSettings, ModuleControlSettings)


@router.put("/modules", response_model=ModuleControlSettings)
async def update_module_control_settings(
    body: ModuleControlSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> ModuleControlSettings:
    await _save_setting(db, _MODULES_KEY, body)
    _record_settings_audit(
        db,
        "settings.modules.update",
        target=_MODULES_KEY,
        details={"disabled": [key for key, enabled in body.model_dump().items() if not enabled]},
    )
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
    general: GeneralAdminSettings
    security: SecuritySettings
    system: SystemAdminSettings
    network_devices: NetworkDeviceAdminSettings
    inventory: InventoryAdminSettings
    alarms_events: AlarmsEventsAdminSettings
    integrations_ai_ops: IntegrationsAiOpsAdminSettings
    lab_operations: LabOperationsAdminSettings
    modules: ModuleControlSettings


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
    def from_role(cls, role: AppRole) -> RoleRead:
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


class AccountAuditPaths(BaseModel):
    user_activity_path: str
    privileged_activity_path: str


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
        tls_min_version=settings.tls_min_version,  # type: ignore[arg-type]  # validated in Settings.validate()
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
async def get_security_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SecuritySettings:
    return await _load_security_settings(db)


@router.patch("/security", response_model=SecuritySettings)
async def update_security_settings(
    body: SecuritySettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SecuritySettings:
    if body.https_enabled and (not body.tls_cert_file or not body.tls_key_file):
        raise HTTPException(status_code=400, detail="HTTPS requires certificate and key file paths")
    row = await db.get(SystemSetting, _SECURITY_KEY)
    if row is None:
        row = SystemSetting(key=_SECURITY_KEY, value=body.model_dump())
        db.add(row)
    else:
        row.value = body.model_dump()
    _record_settings_audit(
        db,
        "settings.security.update",
        target="security",
        details={
            "https_enabled": body.https_enabled,
            "api_auth_enabled": body.api_auth_enabled,
            "root_web_login_enabled": body.root_web_login_enabled,
        },
    )
    return body


@router.get("/profile", response_model=SettingsProfile)
async def export_settings_profile(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
) -> SettingsProfile:
    profile = SettingsProfile(
        general=await _load_setting(db, _GENERAL_KEY, GeneralAdminSettings, GeneralAdminSettings),
        security=await _load_security_settings(db),
        system=await _load_setting(db, _SYSTEM_KEY, SystemAdminSettings, SystemAdminSettings),
        network_devices=await _load_setting(
            db,
            _NETWORK_DEVICES_KEY,
            NetworkDeviceAdminSettings,
            NetworkDeviceAdminSettings,
        ),
        inventory=await _load_setting(
            db,
            _INVENTORY_KEY,
            InventoryAdminSettings,
            InventoryAdminSettings,
        ),
        alarms_events=await _load_setting(
            db,
            _ALARMS_EVENTS_KEY,
            AlarmsEventsAdminSettings,
            AlarmsEventsAdminSettings,
        ),
        integrations_ai_ops=await _load_setting(
            db,
            _INTEGRATIONS_AI_OPS_KEY,
            IntegrationsAiOpsAdminSettings,
            IntegrationsAiOpsAdminSettings,
        ),
        lab_operations=await _load_setting(
            db,
            _LAB_OPERATIONS_KEY,
            LabOperationsAdminSettings,
            LabOperationsAdminSettings,
        ),
        modules=await _load_setting(
            db,
            _MODULES_KEY,
            ModuleControlSettings,
            ModuleControlSettings,
        ),
    )
    _record_settings_audit(db, "settings.profile.export", target="settings-profile")
    return profile


@router.put("/profile", response_model=SettingsProfile)
async def import_settings_profile(
    body: SettingsProfile,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM))],
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
    await _save_setting(db, _GENERAL_KEY, body.general)
    await _save_setting(db, _SYSTEM_KEY, body.system)
    await _save_setting(db, _NETWORK_DEVICES_KEY, body.network_devices)
    await _save_setting(db, _INVENTORY_KEY, body.inventory)
    await _save_setting(db, _ALARMS_EVENTS_KEY, body.alarms_events)
    await _save_setting(db, _INTEGRATIONS_AI_OPS_KEY, body.integrations_ai_ops)
    await _save_setting(db, _LAB_OPERATIONS_KEY, body.lab_operations)
    await _save_setting(db, _MODULES_KEY, body.modules)
    _record_settings_audit(
        db,
        "settings.profile.import",
        target="settings-profile",
        details={"profile_version": body.profile_version},
    )
    return body


@router.get("/audit", response_model=list[AuditLogRead])
async def list_settings_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS))],
    limit: int = 50,
) -> list[AuditLogRead]:
    capped_limit = min(max(limit, 1), 200)
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.object_type == "settings")
        .order_by(AuditLog.timestamp.desc())
        .limit(capped_limit)
    )
    return [AuditLogRead.model_validate(row) for row in result.scalars().all()]


ACCOUNT_AUDIT_EXPORT_COLUMNS = [
    "Timestamp",
    "Actor",
    "Role",
    "Action",
    "Outcome",
    "Source IP",
    "Message",
    "Path",
    "Method",
    "Status Code",
]


def _audit_csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _account_audit_stmt(
    *,
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    role: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    stmt = select(AuditLog).where(AuditLog.object_type == ACCOUNT_AUDIT_OBJECT_TYPE)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if outcome:
        stmt = stmt.where(AuditLog.outcome == outcome)
    if role:
        stmt = stmt.where(AuditLog.details["role"].as_string() == role.lower())
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                AuditLog.actor.ilike(pattern),
                AuditLog.action.ilike(pattern),
                AuditLog.message.ilike(pattern),
                AuditLog.object_id.ilike(pattern),
            )
        )
    if since:
        stmt = stmt.where(AuditLog.timestamp >= since)
    if until:
        stmt = stmt.where(AuditLog.timestamp <= until)
    return stmt


@router.get("/account-audit", response_model=list[AuditLogRead])
async def list_account_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS))],
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    role: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogRead]:
    capped_limit = min(max(limit, 1), 500)
    result = await db.execute(
        _account_audit_stmt(
            actor=actor,
            action=action,
            outcome=outcome,
            role=role,
            q=q,
            since=since,
            until=until,
        )
        .order_by(AuditLog.timestamp.desc())
        .offset(max(offset, 0))
        .limit(capped_limit)
    )
    return [AuditLogRead.model_validate(row) for row in result.scalars().all()]


@router.get("/account-audit/export")
async def export_account_audit(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS))],
    export_format: str = Query("csv", alias="format", pattern="^csv$"),
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    role: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    del export_format
    result = await db.execute(
        _account_audit_stmt(
            actor=actor,
            action=action,
            outcome=outcome,
            role=role,
            q=q,
            since=since,
            until=until,
        ).order_by(AuditLog.timestamp.desc())
    )
    entries = result.scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=ACCOUNT_AUDIT_EXPORT_COLUMNS)
    writer.writeheader()
    for entry in entries:
        details = entry.details or {}
        writer.writerow(
            {
                "Timestamp": _audit_csv_value(entry.timestamp),
                "Actor": _audit_csv_value(entry.actor),
                "Role": _audit_csv_value(details.get("role")),
                "Action": _audit_csv_value(entry.action),
                "Outcome": _audit_csv_value(entry.outcome),
                "Source IP": _audit_csv_value(entry.source_ip),
                "Message": _audit_csv_value(entry.message),
                "Path": _audit_csv_value(details.get("path")),
                "Method": _audit_csv_value(details.get("method")),
                "Status Code": _audit_csv_value(details.get("status_code")),
            }
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="account_audit_export.csv"'},
    )


@router.get("/account-audit/paths", response_model=AccountAuditPaths)
async def get_account_audit_paths(
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_VIEW_AUDIT, PERM_SETTINGS_AUDIT_TRAILS))],
) -> AccountAuditPaths:
    return AccountAuditPaths(
        user_activity_path=settings.account_audit_log_path,
        privileged_activity_path=settings.privileged_account_audit_log_path,
    )


@router.get("/users", response_model=list[UserRead])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> list[UserRead]:
    result = await db.execute(select(AppUser).order_by(AppUser.username))
    return [UserRead.model_validate(user) for user in result.scalars().all()]


@router.get("/permissions")
async def list_permission_catalog(
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> dict[str, list[dict[str, str]]]:
    return PERMISSION_CATALOG


@router.get("/permissions/descriptions")
async def list_permission_descriptions(
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> dict[str, str]:
    return PERMISSION_DESCRIPTIONS


@router.get("/permissions/system-settings")
async def list_system_settings_permissions(
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> list[dict[str, str]]:
    """Table 2: Additional Permissions for System Settings Submenus (EPNM 4.0)."""
    return SYSTEM_SETTINGS_SUBMENUS


@router.get("/roles", response_model=list[RoleRead])
async def list_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> list[RoleRead]:
    await _ensure_builtin_roles(db)
    result = await db.execute(select(AppRole).order_by(AppRole.built_in.desc(), AppRole.name))
    return [RoleRead.from_role(role) for role in result.scalars().all()]


@router.post("/roles", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    body: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> RoleRead:
    existing = await db.execute(select(AppRole).where(AppRole.name == body.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Role already exists")
    role = AppRole(**body.model_dump(), built_in=False)
    db.add(role)
    await db.flush()
    await db.refresh(role)
    _record_settings_audit(
        db,
        "role.create",
        target=str(role.id),
        details={"name": role.name, "user_type": role.user_type, "permissions": role.permissions},
    )
    return RoleRead.from_role(role)


@router.patch("/roles/{id}", response_model=RoleRead)
async def update_role(
    id: uuid.UUID,
    body: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> RoleRead:
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
    _record_settings_audit(
        db,
        "role.update",
        target=str(role.id),
        details={"name": role.name, "user_type": role.user_type, "permissions": role.permissions},
    )
    return RoleRead.from_role(role)


@router.delete("/roles/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> None:
    role = await db.get(AppRole, id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.built_in:
        raise HTTPException(status_code=400, detail="Built-in roles cannot be deleted")
    await db.delete(role)
    _record_settings_audit(db, "role.delete", target=str(id), details={"name": role.name})


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[Principal, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> UserRead:
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
    _record_settings_audit(
        db,
        "user.create",
        target=str(user.id),
        details={"username": user.username, "role": user.role, "user_type": user.user_type},
    )
    await record_account_activity(
        db,
        principal=_principal,
        action="user.privileges.update",
        message=f"User privileges created for {user.username}",
        details={
            "target_username": user.username,
            "target_role": user.role,
            "target_user_type": user.user_type,
            "change_type": "create_user",
        },
    )
    return UserRead.model_validate(user)


@router.patch("/users/{id}", response_model=UserRead)
async def update_user(
    id: uuid.UUID,
    body: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[Principal, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> UserRead:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    previous_role = user.role
    previous_user_type = user.user_type
    previous_permissions = user.custom_permissions or {}
    data = body.model_dump(exclude_unset=True, exclude={"password", "roles"})
    for field, value in data.items():
        setattr(user, field, value)
    if body.roles is not None:
        user.role = ",".join(body.roles)
    if body.password is not None:
        user.password_hash = hash_password(body.password.get_secret_value())
    await db.flush()
    await db.refresh(user)
    _record_settings_audit(
        db,
        "user.update",
        target=str(user.id),
        details={"username": user.username, "role": user.role, "user_type": user.user_type},
    )
    changed_privilege_fields = []
    if previous_role != user.role:
        changed_privilege_fields.append("roles")
    if previous_user_type != user.user_type:
        changed_privilege_fields.append("user_type")
    if body.custom_permissions is not None and previous_permissions != (user.custom_permissions or {}):
        changed_privilege_fields.append("custom_permissions")
    if changed_privilege_fields:
        await record_account_activity(
            db,
            principal=_principal,
            action="user.privileges.update",
            message=f"User privileges changed for {user.username}",
            details={
                "target_username": user.username,
                "target_role": user.role,
                "previous_role": previous_role,
                "target_user_type": user.user_type,
                "previous_user_type": previous_user_type,
                "changed_fields": changed_privilege_fields,
            },
        )
    return UserRead.model_validate(user)


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[object, Depends(require_settings_permission(PERM_SETTINGS_USERS_GROUPS, PERM_SETTINGS_USER_ADMIN_USERS_GROUPS))],
) -> None:
    user = await db.get(AppUser, id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    _record_settings_audit(db, "user.delete", target=str(id), details={"username": user.username})
