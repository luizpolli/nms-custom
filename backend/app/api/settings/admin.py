"""Admin settings endpoints: general / system / network / inventory / alarms /
integrations / lab / modules.

These are simple GET/PUT pairs that persist a single JSON blob keyed by the
section name.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.security.auth import (
    PERM_SETTINGS_ALARMS_EVENTS,
    PERM_SETTINGS_NETWORK_SNMP,
    PERM_SETTINGS_SYSTEM,
    require_settings_permission,
)

from ._schemas import (
    _ALARMS_EVENTS_KEY,
    _GENERAL_KEY,
    _INTEGRATIONS_AI_OPS_KEY,
    _INVENTORY_KEY,
    _LAB_OPERATIONS_KEY,
    _MODULES_KEY,
    _NETWORK_DEVICES_KEY,
    _SYSTEM_KEY,
    AlarmsEventsAdminSettings,
    GeneralAdminSettings,
    IntegrationsAiOpsAdminSettings,
    InventoryAdminSettings,
    LabOperationsAdminSettings,
    ModuleControlSettings,
    NetworkDeviceAdminSettings,
    SettingsTestResult,
    SystemAdminSettings,
    SystemMailSettings,
    _load_setting,
    _record_settings_audit,
    _save_setting,
    _test_mail_settings,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# General settings
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
# System settings
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
# Network device settings
# ---------------------------------------------------------------------------


@router.get("/network-devices", response_model=NetworkDeviceAdminSettings)
async def get_network_device_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_NETWORK_SNMP)),
    ],
) -> NetworkDeviceAdminSettings:
    return await _load_setting(
        db, _NETWORK_DEVICES_KEY, NetworkDeviceAdminSettings, NetworkDeviceAdminSettings
    )


@router.put("/network-devices", response_model=NetworkDeviceAdminSettings)
async def update_network_device_settings(
    body: NetworkDeviceAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_NETWORK_SNMP)),
    ],
) -> NetworkDeviceAdminSettings:
    await _save_setting(db, _NETWORK_DEVICES_KEY, body)
    _record_settings_audit(db, "settings.network_devices.update", target=_NETWORK_DEVICES_KEY)
    return body


# ---------------------------------------------------------------------------
# Inventory settings
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
# Alarms / Events settings
# ---------------------------------------------------------------------------


@router.get("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def get_alarms_events_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_ALARMS_EVENTS)),
    ],
) -> AlarmsEventsAdminSettings:
    return await _load_setting(
        db, _ALARMS_EVENTS_KEY, AlarmsEventsAdminSettings, AlarmsEventsAdminSettings
    )


@router.put("/alarms-events", response_model=AlarmsEventsAdminSettings)
async def update_alarms_events_settings(
    body: AlarmsEventsAdminSettings,
    db: Annotated[AsyncSession, Depends(get_db)],
    _principal: Annotated[
        object,
        Depends(require_settings_permission(PERM_SETTINGS_SYSTEM, PERM_SETTINGS_ALARMS_EVENTS)),
    ],
) -> AlarmsEventsAdminSettings:
    await _save_setting(db, _ALARMS_EVENTS_KEY, body)
    _record_settings_audit(db, "settings.alarms_events.update", target=_ALARMS_EVENTS_KEY)
    return body


# ---------------------------------------------------------------------------
# Integrations / AI Ops settings
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
    _record_settings_audit(
        db, "settings.integrations_ai_ops.update", target=_INTEGRATIONS_AI_OPS_KEY
    )
    return body


# ---------------------------------------------------------------------------
# Lab / Operations settings
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
# Module control settings
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
