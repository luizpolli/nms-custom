"""System settings + local user administration API.

The original ``settings.py`` (1.3k lines) was split into focused sub-modules:

* ``admin``           - section CRUD: general/system/network/inventory/alarms/
                        integrations/lab/modules
* ``security_profile``- security settings + full profile export/import
* ``audit``           - settings audit log + account audit (list/export/paths)
* ``users_roles``     - users, roles, permission catalog

This package re-exports the public symbols other modules rely on (``router``
and a few Pydantic schemas used by the OpenAPI surface and a handful of
tests). The legacy import path ``app.api.settings.SecuritySettings`` etc.
keeps working through these re-exports.
"""

from __future__ import annotations

from fastapi import APIRouter

# Re-export schemas/helpers so existing imports keep working.
from ._schemas import (  # noqa: F401  (re-exports for callers/tests)
    AccountAuditPaths,
    AlarmNotificationSettings,
    AlarmsEventsAdminSettings,
    AlarmSeverityMapping,
    AlarmSuppressionSettings,
    GeneralAdminSettings,
    IntegrationsAiOpsAdminSettings,
    InventoryAdminSettings,
    LabOperationsAdminSettings,
    ModuleControlSettings,
    NetworkCliSettings,
    NetworkDeviceAdminSettings,
    NetworkSnmpSettings,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    SecuritySettings,
    SettingsProfile,
    SettingsTestResult,
    SystemAdminSettings,
    SystemJobSettings,
    SystemMailSettings,
    SystemRetentionSettings,
    UserCreate,
    UserRead,
    UserUpdate,
)
from .admin import router as _admin_router
from .audit import router as _audit_router
from .security_profile import router as _security_profile_router
from .users_roles import router as _users_roles_router

# Combined router preserves the exact URL surface served by the previous
# monolithic module. Order matches the legacy file so the OpenAPI doc tag
# ordering is unchanged.
router = APIRouter()
router.include_router(_admin_router)
router.include_router(_security_profile_router)
router.include_router(_audit_router)
router.include_router(_users_roles_router)

__all__ = [
    "AccountAuditPaths",
    "AlarmNotificationSettings",
    "AlarmSeverityMapping",
    "AlarmSuppressionSettings",
    "AlarmsEventsAdminSettings",
    "GeneralAdminSettings",
    "IntegrationsAiOpsAdminSettings",
    "InventoryAdminSettings",
    "LabOperationsAdminSettings",
    "ModuleControlSettings",
    "NetworkCliSettings",
    "NetworkDeviceAdminSettings",
    "NetworkSnmpSettings",
    "RoleCreate",
    "RoleRead",
    "RoleUpdate",
    "SecuritySettings",
    "SettingsProfile",
    "SettingsTestResult",
    "SystemAdminSettings",
    "SystemJobSettings",
    "SystemMailSettings",
    "SystemRetentionSettings",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "router",
]
