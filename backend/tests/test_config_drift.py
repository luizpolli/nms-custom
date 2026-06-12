"""Tests for config backup collection, golden promotion, and drift detection."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import app.api.devices.config_ops as config_ops
from app.api.devices.config_ops import (
    GoldenPromoteRequest,
    collect_config_backup,
    diff_config_backup,
    get_config_drift,
    promote_golden_config,
)
from app.models.config_backup import ConfigBackup
from app.models.device import Device
from app.security.auth import Principal
from app.services.config_drift import (
    config_hash,
    drift_summary,
    normalize_config,
    unified_config_diff,
)
from app.services.ssh.client import SSHCredential

_XE_CONFIG = """Building configuration...

Current configuration : 4096 bytes
!
! Last configuration change at 10:00:01 UTC Thu Jun 11 2026 by admin
!
hostname edge-920
!
interface GigabitEthernet0/0/1
 description uplink
 no shutdown
!
ntp clock-period 17179869
end
"""

_XR_CONFIG = """!! IOS XR Configuration 7.5.2
!! Last configuration change at Thu Jun 11 10:00:01 2026 by admin
!
hostname core-ncs
interface TenGigE0/0/0/0
 description core-link
!
end
"""


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


def test_normalize_strips_xe_volatile_lines():
    normalized = normalize_config(_XE_CONFIG)
    assert "Building configuration" not in normalized
    assert "Current configuration" not in normalized
    assert "Last configuration change" not in normalized
    assert "ntp clock-period" not in normalized
    assert "hostname edge-920" in normalized
    assert normalized.startswith("!")


def test_normalize_strips_xr_volatile_lines():
    normalized = normalize_config(_XR_CONFIG)
    assert "Last configuration change" not in normalized
    assert "IOS XR Configuration" not in normalized
    assert "hostname core-ncs" in normalized


def test_hash_stable_across_volatile_only_changes():
    later = _XE_CONFIG.replace(
        "10:00:01 UTC Thu Jun 11 2026", "23:59:59 UTC Fri Jun 12 2026"
    ).replace("ntp clock-period 17179869", "ntp clock-period 17179870")
    assert config_hash(normalize_config(_XE_CONFIG)) == config_hash(normalize_config(later))


def test_hash_changes_on_real_config_change():
    changed = _XE_CONFIG.replace(" no shutdown", " shutdown")
    assert config_hash(normalize_config(_XE_CONFIG)) != config_hash(normalize_config(changed))


def test_unified_diff_identical_is_empty():
    a = normalize_config(_XE_CONFIG)
    assert unified_config_diff(a, a, "a", "b") == ""


def test_unified_diff_and_summary_count_changes():
    old = normalize_config(_XE_CONFIG)
    new = normalize_config(_XE_CONFIG.replace(" no shutdown", " shutdown"))
    diff = unified_config_diff(old, new, "golden", "backup")
    assert "- no shutdown" in diff
    assert "+ shutdown" in diff
    assert drift_summary(diff) == {"added": 1, "removed": 1}


# ---------------------------------------------------------------------------
# Endpoint tests (fake session, queued results)
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = list(rows or [])

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    """Returns queued scalar results in execute() call order."""

    def __init__(self, scalars: list):
        self._scalars = list(scalars)
        self.added = []
        self.flushed = False

    async def execute(self, *args, **kwargs):
        return _FakeResult(scalar=self._scalars.pop(0))

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed = True


class _FakeSSHClient:
    raw_config = _XE_CONFIG

    def __init__(self, credential):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def backup_config(self, device_type: str = "ios-xr") -> str:
        return type(self).raw_config


_PRINCIPAL = Principal(subject="api-key", role="admin")


def _device() -> Device:
    return Device(
        id=uuid.uuid4(),
        name="edge-1",
        ip_address="10.0.0.1",
        device_type="router",
        model="ASR-920-12CZ-D",
        vendor="Cisco",
    )


def _backup(device_id, content: str, kind: str = "backup", age_minutes: int = 0) -> ConfigBackup:
    normalized = normalize_config(content)
    return ConfigBackup(
        id=uuid.uuid4(),
        device_id=device_id,
        kind=kind,
        content=normalized,
        content_hash=config_hash(normalized),
        size_bytes=len(normalized.encode()),
        collected_by="test",
        created_at=datetime.now() - timedelta(minutes=age_minutes),
    )


@pytest.fixture(autouse=True)
def _patch_ssh(monkeypatch):
    monkeypatch.setattr(
        config_ops,
        "ssh_credential_for_device",
        lambda device: SSHCredential(host=device.ip_address, username="test"),
    )
    monkeypatch.setattr(config_ops, "SSHClient", _FakeSSHClient)
    _FakeSSHClient.raw_config = _XE_CONFIG


@pytest.mark.asyncio
async def test_collect_stores_normalized_backup():
    device = _device()
    session = _FakeSession([device, None])  # device, no previous backup

    result = await collect_config_backup(device.id, session, _PRINCIPAL)

    assert result["deduplicated"] is False
    assert session.flushed
    (stored,) = session.added
    assert stored.kind == "backup"
    assert "Building configuration" not in stored.content
    assert stored.content_hash == config_hash(normalize_config(_XE_CONFIG))


@pytest.mark.asyncio
async def test_collect_dedupes_unchanged_config():
    device = _device()
    existing = _backup(device.id, _XE_CONFIG)
    # Same config, different volatile timestamp → same hash → dedupe.
    _FakeSSHClient.raw_config = _XE_CONFIG.replace("Jun 11 2026", "Jun 12 2026")
    session = _FakeSession([device, existing])

    result = await collect_config_backup(device.id, session, _PRINCIPAL)

    assert result["deduplicated"] is True
    assert result["id"] == str(existing.id)
    assert session.added == []


@pytest.mark.asyncio
async def test_drift_without_golden():
    device = _device()
    session = _FakeSession([device, None, _backup(device.id, _XE_CONFIG)])

    result = await get_config_drift(device.id, session, _PRINCIPAL)

    assert result["status"] == "no_golden"


@pytest.mark.asyncio
async def test_drift_in_sync_and_drifted():
    device = _device()
    golden = _backup(device.id, _XE_CONFIG, kind="golden")

    session = _FakeSession([device, golden, _backup(device.id, _XE_CONFIG)])
    result = await get_config_drift(device.id, session, _PRINCIPAL)
    assert result["status"] == "in_sync"
    assert result["diff"] == ""

    drifted = _backup(device.id, _XE_CONFIG.replace(" no shutdown", " shutdown"))
    session = _FakeSession([device, golden, drifted])
    result = await get_config_drift(device.id, session, _PRINCIPAL)
    assert result["status"] == "drift"
    assert result["added"] == 1
    assert result["removed"] == 1
    assert "+ shutdown" in result["diff"]


@pytest.mark.asyncio
async def test_promote_golden_copies_backup():
    device = _device()
    backup = _backup(device.id, _XE_CONFIG)
    session = _FakeSession([device, backup])

    result = await promote_golden_config(
        device.id, GoldenPromoteRequest(backup_id=backup.id), session, _PRINCIPAL
    )

    assert result["kind"] == "golden"
    (golden,) = session.added
    assert golden.kind == "golden"
    assert golden.content_hash == backup.content_hash


@pytest.mark.asyncio
async def test_promote_golden_missing_backup_404():
    device = _device()
    session = _FakeSession([device, None])

    with pytest.raises(HTTPException) as exc:
        await promote_golden_config(
            device.id, GoldenPromoteRequest(backup_id=uuid.uuid4()), session, _PRINCIPAL
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_diff_against_previous():
    device = _device()
    newer = _backup(device.id, _XE_CONFIG.replace(" no shutdown", " shutdown"))
    older = _backup(device.id, _XE_CONFIG, age_minutes=60)
    session = _FakeSession([device, newer, older])

    result = await diff_config_backup(device.id, newer.id, session, _PRINCIPAL, against="previous")

    assert result["identical"] is False
    assert result["baseId"] == str(older.id)
    assert "+ shutdown" in result["diff"]


@pytest.mark.asyncio
async def test_diff_against_golden_missing_404():
    device = _device()
    backup = _backup(device.id, _XE_CONFIG)
    session = _FakeSession([device, backup, None])

    with pytest.raises(HTTPException) as exc:
        await diff_config_backup(device.id, backup.id, session, _PRINCIPAL, against="golden")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_diff_against_invalid_token_422():
    device = _device()
    backup = _backup(device.id, _XE_CONFIG)
    session = _FakeSession([device, backup])

    with pytest.raises(HTTPException) as exc:
        await diff_config_backup(device.id, backup.id, session, _PRINCIPAL, against="not-a-uuid")
    assert exc.value.status_code == 422
