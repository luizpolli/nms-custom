"""Shared schemas, constants, and helpers for the settings API package.

Everything that is referenced by more than one sub-router lives here so the
individual route modules stay small and focused. Kept private (``_schemas``)
because external callers should not depend on this surface directly.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.permissions_catalog import BUILT_IN_ROLES, all_permission_keys
from app.config import settings
from app.models.audit import AuditLog
from app.models.system import AppRole, SystemSetting
from app.security.audit import audit
from app.services.account_audit import ACCOUNT_AUDIT_OBJECT_TYPE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

_S = TypeVar("_S", bound=BaseModel)


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------


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
# General settings
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
# Inventory settings
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
# Alarms / Events settings
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
    """Admin-facing AI Ops toggle. Connection details (provider, model, base
    URL, API key) are infrastructure config and live only in AI_OPS_LLM_*
    environment variables — see IntegrationsAiOpsAdminSettingsResponse for
    the read-only effective_* fields that mirror what's actually running.
    """

    ai_ops_enabled: bool = True


class IntegrationsAiOpsAdminSettingsResponse(IntegrationsAiOpsAdminSettings):
    """GET-only view: admin toggle plus the live env-driven config it gates."""

    effective_llm_enabled: bool
    effective_llm_provider: str
    effective_llm_model: str
    effective_llm_base_url: str


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
# Security settings
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Settings profile (full export/import bundle)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# User / role schemas + validators
# ---------------------------------------------------------------------------


def _validate_permissions(values: dict[str, bool]) -> dict[str, bool]:
    allowed = all_permission_keys()
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
    return values


def _validate_password_strength(
    password: SecretStr,
    username: str | None = None,
    display_name: str | None = None,
) -> SecretStr:
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


# ---------------------------------------------------------------------------
# DB load/save helpers + security defaults
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


async def _load_security_settings(db: AsyncSession) -> SecuritySettings:
    row = await db.get(SystemSetting, _SECURITY_KEY)
    if not row:
        return _defaults()
    return SecuritySettings(**{**_defaults().model_dump(), **row.value})


async def _ensure_builtin_roles(db: AsyncSession) -> None:
    for name, spec in BUILT_IN_ROLES.items():
        result = await db.execute(select(AppRole).where(AppRole.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            db.add(
                AppRole(
                    name=name,
                    description=spec["description"],
                    user_type=spec["user_type"],
                    permissions=spec["permissions"],
                    built_in=True,
                )
            )
        else:
            role.description = spec["description"]
            role.user_type = spec["user_type"]
            # Preserve customized permissions for editable built-ins; reset locked ones.
            if not spec.get("editable", True) or not role.permissions:
                role.permissions = spec["permissions"]
            role.built_in = True
    # Flush so the SELECT below sees the newly added rows in the same transaction.
    await db.flush()


# ---------------------------------------------------------------------------
# Account audit helpers (shared between list/export)
# ---------------------------------------------------------------------------


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
