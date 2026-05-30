"""Security settings + full settings-profile import/export endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.system import SystemSetting
from app.security.auth import PERM_SETTINGS_SYSTEM, require_settings_permission

from ._schemas import (
    _ALARMS_EVENTS_KEY,
    _GENERAL_KEY,
    _INTEGRATIONS_AI_OPS_KEY,
    _INVENTORY_KEY,
    _LAB_OPERATIONS_KEY,
    _MODULES_KEY,
    _NETWORK_DEVICES_KEY,
    _PROFILE_VERSION,
    _SECURITY_KEY,
    _SYSTEM_KEY,
    AlarmsEventsAdminSettings,
    GeneralAdminSettings,
    IntegrationsAiOpsAdminSettings,
    InventoryAdminSettings,
    LabOperationsAdminSettings,
    ModuleControlSettings,
    NetworkDeviceAdminSettings,
    SecuritySettings,
    SettingsProfile,
    SystemAdminSettings,
    _load_security_settings,
    _load_setting,
    _record_settings_audit,
    _save_setting,
)

router = APIRouter()


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
