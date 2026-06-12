"""Tests for the interface admin-status (shutdown / no shutdown) endpoint."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

import app.api.devices.interface_ops as interface_ops
from app.api.devices.interface_ops import (
    AdminStatusRequest,
    _build_admin_status_commands,
    _is_ios_xr,
    set_interface_admin_status,
)
from app.models.device import Device
from app.models.interface import Interface
from app.security.auth import PERM_INTERFACES_ADMIN, Principal
from app.services.ssh.client import CommandResult, SSHCredential


class _FakeResult:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar


class _FakeSession:
    """call 1 → device lookup, call 2 → interface lookup."""

    def __init__(self, device: Device | None, interface: Interface | None):
        self.device = device
        self.interface = interface
        self.calls = 0
        self.added = []
        self.flushed = False

    async def execute(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return _FakeResult(scalar=self.device)
        return _FakeResult(scalar=self.interface)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True


class _FakeSSHClient:
    """Records the config session commands and returns a canned result."""

    last_commands: list[str] | None = None
    canned = CommandResult(stdout="", stderr="", exit_status=0, duration_ms=1.0)

    def __init__(self, credential):
        self.credential = credential

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def run_config_session(self, commands, timeout: int = 60):
        type(self).last_commands = list(commands)
        return type(self).canned


def _device(**overrides) -> Device:
    defaults = dict(
        id=uuid.uuid4(),
        name="edge-1",
        ip_address="10.0.0.1",
        device_type="router",
        vendor="Cisco",
    )
    defaults.update(overrides)
    return Device(**defaults)


def _interface(device: Device, name: str = "GigabitEthernet0/0/1") -> Interface:
    return Interface(id=uuid.uuid4(), device_id=device.id, name=name, admin_status="up")


_PRINCIPAL = Principal(subject="api-key", role="admin")


@pytest.fixture(autouse=True)
def _patch_ssh(monkeypatch):
    monkeypatch.setattr(
        interface_ops,
        "ssh_credential_for_device",
        lambda device: SSHCredential(host=device.ip_address, username="test"),
    )
    monkeypatch.setattr(interface_ops, "SSHClient", _FakeSSHClient)
    _FakeSSHClient.last_commands = None
    _FakeSSHClient.canned = CommandResult(stdout="", stderr="", exit_status=0, duration_ms=1.0)


# ---------------------------------------------------------------------------
# OS detection and command building
# ---------------------------------------------------------------------------


def test_is_ios_xr_detects_ncs_and_asr9k_but_not_asr920():
    assert _is_ios_xr(_device(model="NCS-55A1-36H-SE-S"))
    assert _is_ios_xr(_device(model="Cisco ASR-9010 Router"))
    assert _is_ios_xr(_device(os_type="IOS XR", model=None))
    assert not _is_ios_xr(_device(model="ASR-920-12CZ-D"))
    assert not _is_ios_xr(_device(os_type="ios-xe", model="NCS-mislabeled"))


def test_command_sequence_xr_uses_commit():
    device = _device(model="N540X-12Z16G-SYS-D")
    cmds = _build_admin_status_commands(device, "TenGigE0/0/0/0", "disable")
    assert cmds == [
        "configure terminal",
        "interface TenGigE0/0/0/0",
        "shutdown",
        "commit",
        "end",
    ]


def test_command_sequence_xe_uses_write_memory():
    device = _device(model="ASR-920-12SZ-IM", os_type="ios-xe")
    cmds = _build_admin_status_commands(device, "GigabitEthernet0/0/1", "enable")
    assert cmds == [
        "configure terminal",
        "interface GigabitEthernet0/0/1",
        "no shutdown",
        "end",
        "write memory",
    ]


# ---------------------------------------------------------------------------
# Endpoint behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disable_success_updates_admin_status():
    device = _device(model="ASR-920-12CZ-D", os_type="ios-xe")
    iface = _interface(device)
    session = _FakeSession(device, iface)

    result = await set_interface_admin_status(
        device.id, iface.id, AdminStatusRequest(action="disable"), session, _PRINCIPAL
    )

    assert result["success"] is True
    assert result["action"] == "disable"
    assert result["adminStatus"] == "down"
    assert iface.admin_status == "down"
    assert session.flushed
    assert _FakeSSHClient.last_commands is not None
    assert "shutdown" in _FakeSSHClient.last_commands
    assert "write memory" in _FakeSSHClient.last_commands


@pytest.mark.asyncio
async def test_enable_success_on_xr_device():
    device = _device(model="NCS560-4")
    iface = _interface(device, name="TenGigE0/0/0/5")
    session = _FakeSession(device, iface)

    result = await set_interface_admin_status(
        device.id, iface.id, AdminStatusRequest(action="enable"), session, _PRINCIPAL
    )

    assert result["success"] is True
    assert iface.admin_status == "up"
    assert "no shutdown" in _FakeSSHClient.last_commands
    assert "commit" in _FakeSSHClient.last_commands


@pytest.mark.asyncio
async def test_cli_error_marks_failure_and_keeps_admin_status():
    device = _device(model="ASR-920-12SZ-D", os_type="ios-xe")
    iface = _interface(device)
    session = _FakeSession(device, iface)
    _FakeSSHClient.canned = CommandResult(
        stdout="% Invalid input detected at '^' marker.",
        stderr="",
        exit_status=0,
        duration_ms=1.0,
    )

    result = await set_interface_admin_status(
        device.id, iface.id, AdminStatusRequest(action="disable"), session, _PRINCIPAL
    )

    assert result["success"] is False
    assert iface.admin_status == "up"
    assert not session.flushed


@pytest.mark.asyncio
async def test_ssh_connection_error_marks_failure():
    device = _device(model="NCS-5501")
    iface = _interface(device, name="HundredGigE0/0/1/0")
    session = _FakeSession(device, iface)
    _FakeSSHClient.canned = CommandResult(
        stdout="", stderr="", exit_status=1, duration_ms=1.0, error="connection refused"
    )

    result = await set_interface_admin_status(
        device.id, iface.id, AdminStatusRequest(action="enable"), session, _PRINCIPAL
    )

    assert result["success"] is False
    assert result["error"] == "connection refused"
    assert iface.admin_status == "up"


@pytest.mark.asyncio
async def test_interface_not_found_returns_404():
    device = _device()
    session = _FakeSession(device, None)

    with pytest.raises(HTTPException) as exc:
        await set_interface_admin_status(
            device.id, uuid.uuid4(), AdminStatusRequest(action="disable"), session, _PRINCIPAL
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_non_physical_interface_name_rejected():
    device = _device()
    iface = _interface(device, name="Gi0/0/1; reload")
    session = _FakeSession(device, iface)

    with pytest.raises(HTTPException) as exc:
        await set_interface_admin_status(
            device.id, iface.id, AdminStatusRequest(action="disable"), session, _PRINCIPAL
        )
    assert exc.value.status_code == 422
    assert _FakeSSHClient.last_commands is None


@pytest.mark.asyncio
async def test_missing_credential_returns_422(monkeypatch):
    device = _device()
    iface = _interface(device)
    session = _FakeSession(device, iface)

    def _raise(_device):
        raise ValueError("Device has no credential attached")

    monkeypatch.setattr(interface_ops, "ssh_credential_for_device", _raise)

    with pytest.raises(HTTPException) as exc:
        await set_interface_admin_status(
            device.id, iface.id, AdminStatusRequest(action="disable"), session, _PRINCIPAL
        )
    assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_admin_status_permission_is_admin_only():
    assert Principal(subject="k", role="root").has_command_perm(PERM_INTERFACES_ADMIN)
    assert Principal(subject="k", role="admin").has_command_perm(PERM_INTERFACES_ADMIN)
    assert not Principal(subject="k", role="operator").has_command_perm(PERM_INTERFACES_ADMIN)
    assert not Principal(subject="k", role="ai-ops").has_command_perm(PERM_INTERFACES_ADMIN)
    assert not Principal(subject="k", role="viewer").has_command_perm(PERM_INTERFACES_ADMIN)
