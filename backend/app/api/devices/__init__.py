"""Device API routes, assembled from focused submodules.

All submodules decorate the shared router defined in ``common``. They are
imported via ``importlib`` below (not plain imports) so that linters cannot
re-sort them: import order IS route registration order, and literal paths
(``/export``, ``/bulk``, ``/verify-credentials``) must register before the
``/{id}`` routes or the UUID path parameter shadows them.
"""

from __future__ import annotations

import importlib

from app.api.devices.common import _build_snmp_cred, _get_device_or_404, router, settings

# Re-exported for backwards compatibility: tests patch
# ``app.api.devices.CredentialVault`` and import the chassis helpers below.
from app.security.crypto import CredentialVault

for _submodule in (
    "export",
    "bulk_import",
    "snmp_ops",
    "crud",
    "chassis",
    "interface_ops",
    "config_ops",
):
    importlib.import_module(f"app.api.devices.{_submodule}")

from app.api.devices.chassis import (  # noqa: E402
    CHASSIS_PID_PROFILES,
    CHASSIS_PROFILE_FILES,
    _apply_physical_inventory_to_chassis,
    _chassis_pid_for_device,
    _chassis_profile_for_device,
    _customize_chassis_model,
    _load_chassis_profile,
    _upsert_physical_inventory_components,
    get_device_chassis,
)

__all__ = [
    "CHASSIS_PID_PROFILES",
    "CHASSIS_PROFILE_FILES",
    "CredentialVault",
    "_apply_physical_inventory_to_chassis",
    "_build_snmp_cred",
    "_chassis_pid_for_device",
    "_chassis_profile_for_device",
    "_customize_chassis_model",
    "_get_device_or_404",
    "_load_chassis_profile",
    "_upsert_physical_inventory_components",
    "get_device_chassis",
    "router",
    "settings",
]
