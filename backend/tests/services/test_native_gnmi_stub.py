"""Tests for the native gNMI contract and stub adapter."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

import pytest

from app.services.telemetry.native_gnmi import (
    GnmiSubscriptionConfig,
    GnmiTLSConfig,
    StubNativeGnmiAdapter,
    build_stub_from_paths,
    make_lab_subscription,
    validate_native_gnmi_tls,
)


def test_validate_native_gnmi_tls_requires_tls():
    cfg = GnmiSubscriptionConfig(target="r1", paths=("/p",))
    with pytest.raises(ValueError):
        validate_native_gnmi_tls(cfg)


def test_validate_native_gnmi_tls_requires_client_material_for_mtls():
    cfg = GnmiSubscriptionConfig(
        target="r1",
        paths=("/p",),
        tls=GnmiTLSConfig(ca_cert=Path("/etc/ca.pem"), require_mutual_tls=True),
    )
    with pytest.raises(ValueError):
        validate_native_gnmi_tls(cfg)


def test_make_lab_subscription_is_mtls_safe():
    cfg = make_lab_subscription("r1.lab", ("/interfaces",))
    validate_native_gnmi_tls(cfg)
    assert cfg.tls is not None
    assert cfg.tls.require_mutual_tls is True


def test_stub_adapter_yields_one_sample_per_path():
    paths = ("/interfaces/counters", "/cpu/usage")
    adapter = build_stub_from_paths(paths, start_value=10.0, step=5.0)
    device_id = uuid.uuid4()
    cfg = GnmiSubscriptionConfig(target="r1", device_id=device_id, paths=paths)

    async def _collect():
        return [s async for s in adapter.subscribe(cfg)]

    samples = asyncio.run(_collect())
    assert [s.path for s in samples] == list(paths)
    assert [s.value for s in samples] == [10.0, 15.0]
    assert all(s.device_id == device_id for s in samples)


def test_stub_adapter_is_replayable_across_subscribes():
    adapter = StubNativeGnmiAdapter([])
    cfg = GnmiSubscriptionConfig(target="r1")

    async def _collect():
        return [s async for s in adapter.subscribe(cfg)]

    assert asyncio.run(_collect()) == []
    assert asyncio.run(_collect()) == []
