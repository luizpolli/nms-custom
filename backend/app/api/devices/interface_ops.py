"""Interface administrative operations — enable/disable ports over SSH.

The CLI sent to the device is built entirely server-side from an enum
action plus the interface name stored in the database (validated against a
strict pattern), so the user-supplied COMMAND_ALLOWLIST for ad-hoc commands
does not apply here; authorization is enforced through the dedicated
``interfaces:admin_status`` permission instead (root/admin only).
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.devices.common import _get_device_or_404, router
from app.database import get_db
from app.models.device import Device
from app.models.interface import Interface
from app.security.audit import audit
from app.security.auth import (
    PERM_INTERFACES_ADMIN,
    Principal,
    require_command_permission,
)
from app.services.ssh.client import SSHClient
from app.services.ssh.command_runner import ssh_credential_for_device

_INTERFACE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z-]{0,47}\d+(?:/\d+){0,4}(?:\.\d+)?$")
# XR platforms: explicit "xr" os token, NCS family (incl. N540x/N560x PIDs),
# or 4-digit ASR9k chassis (must NOT match ASR-920, which is IOS XE).
_XR_MODEL_RE = re.compile(r"\bncs|\bn5[46]0|\basr[- ]?9\d{3}\b", re.IGNORECASE)
_CLI_ERROR_RE = re.compile(
    r"^%+\s*(?:invalid|incomplete|ambiguous|unknown|error|failed)",
    re.IGNORECASE | re.MULTILINE,
)


class AdminStatusRequest(BaseModel):
    action: Literal["enable", "disable"]


def _is_ios_xr(device: Device) -> bool:
    explicit = " ".join(
        filter(None, [device.os_type, device.device_type, device.platform_family])
    ).lower()
    if "xr" in explicit:
        return True
    if "xe" in explicit:
        return False
    return bool(_XR_MODEL_RE.search(device.model or ""))


def _build_admin_status_commands(device: Device, interface_name: str, action: str) -> list[str]:
    """Build the per-OS config sequence for a single interactive session."""
    toggle = "no shutdown" if action == "enable" else "shutdown"
    if _is_ios_xr(device):
        return ["configure terminal", f"interface {interface_name}", toggle, "commit", "end"]
    return ["configure terminal", f"interface {interface_name}", toggle, "end", "write memory"]


@router.post("/{id}/interfaces/{interface_id}/admin-status")
async def set_interface_admin_status(
    id: uuid.UUID,
    interface_id: uuid.UUID,
    body: AdminStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[Principal, Depends(require_command_permission(PERM_INTERFACES_ADMIN))],
) -> dict[str, object]:
    """Enable (no shutdown) or disable (shutdown) an interface via SSH."""
    device = await _get_device_or_404(db, id)

    iface_result = await db.execute(
        select(Interface).where(Interface.id == interface_id, Interface.device_id == id)
    )
    interface = iface_result.scalar_one_or_none()
    if interface is None:
        raise HTTPException(status_code=404, detail="Interface not found for this device")

    if not _INTERFACE_NAME_RE.fullmatch(interface.name):
        raise HTTPException(
            status_code=422,
            detail=f"Interface name {interface.name!r} is not a configurable physical interface",
        )

    try:
        ssh_cred = ssh_credential_for_device(device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    commands = _build_admin_status_commands(device, interface.name, body.action)
    async with SSHClient(ssh_cred) as client:
        result = await client.run_config_session(commands)

    success = (
        result.error is None
        and result.exit_status == 0
        and not _CLI_ERROR_RE.search(result.stdout)
    )

    audit(
        "interface.admin_status",
        actor=principal.subject,
        target=f"{device.id}:{interface.name}",
        role=principal.role,
        requested_action=body.action,
        success=success,
        exit_status=result.exit_status,
    )

    if success:
        interface.admin_status = "up" if body.action == "enable" else "down"
        db.add(interface)
        await db.flush()

    return {
        "interfaceName": interface.name,
        "action": body.action,
        "success": success,
        "adminStatus": interface.admin_status,
        "output": result.stdout[-4096:],
        "error": result.error,
    }
