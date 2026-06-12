"""Tests for SNMPv3 USM user support in the trap receiver."""

from __future__ import annotations

import json

import pytest

from app.services.snmp import trap_receiver
from app.services.snmp.trap_receiver import (
    AUTH_PROTOCOLS,
    PRIV_PROTOCOLS,
    TrapV3User,
    parse_trap_v3_users,
)

_FULL_USER = {
    "user": "nms-trap",
    "auth_protocol": "SHA256",
    "auth_key": "authpass123",
    "priv_protocol": "AES128",
    "priv_key": "privpass123",
    "engine_id": "80000009030000112233445566",
}


# ---------------------------------------------------------------------------
# parse_trap_v3_users
# ---------------------------------------------------------------------------


def test_parse_empty_returns_no_users():
    assert parse_trap_v3_users("") == []
    assert parse_trap_v3_users("   ") == []


def test_parse_full_user():
    (user,) = parse_trap_v3_users(json.dumps([_FULL_USER]))
    assert user == TrapV3User(
        user="nms-trap",
        auth_protocol="SHA256",
        auth_key="authpass123",
        priv_protocol="AES128",
        priv_key="privpass123",
        engine_id="80000009030000112233445566",
    )


def test_parse_minimal_noauth_user():
    (user,) = parse_trap_v3_users(json.dumps([{"user": "ro-trap"}]))
    assert user.user == "ro-trap"
    assert user.auth_protocol is None
    assert user.priv_protocol is None
    assert user.engine_id is None


def test_parse_normalizes_protocol_case():
    (user,) = parse_trap_v3_users(
        json.dumps([{"user": "u", "auth_protocol": "sha256", "auth_key": "k" * 8}])
    )
    assert user.auth_protocol == "SHA256"


def test_parse_invalid_json_raises():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_trap_v3_users("{broken")


def test_parse_non_list_raises():
    with pytest.raises(ValueError, match="JSON list"):
        parse_trap_v3_users(json.dumps({"user": "x"}))


def test_parse_missing_user_field_raises():
    with pytest.raises(ValueError, match=r"TRAP_V3_USERS\[0\]"):
        parse_trap_v3_users(json.dumps([{"auth_key": "k"}]))


def test_parse_unknown_auth_protocol_raises():
    with pytest.raises(ValueError, match="auth_protocol"):
        parse_trap_v3_users(json.dumps([{"user": "u", "auth_protocol": "CRC32"}]))


def test_parse_unknown_priv_protocol_raises():
    with pytest.raises(ValueError, match="priv_protocol"):
        parse_trap_v3_users(json.dumps([{"user": "u", "priv_protocol": "ROT13"}]))


def test_parse_priv_without_auth_raises():
    with pytest.raises(ValueError, match="authPriv"):
        parse_trap_v3_users(json.dumps([{"user": "u", "priv_key": "secret123"}]))


def test_parse_bad_engine_id_raises():
    with pytest.raises(ValueError, match="engine_id"):
        parse_trap_v3_users(json.dumps([{"user": "u", "engine_id": "not-hex"}]))
    with pytest.raises(ValueError, match="engine_id"):
        parse_trap_v3_users(json.dumps([{"user": "u", "engine_id": "abc"}]))  # odd length


# ---------------------------------------------------------------------------
# USM registration
# ---------------------------------------------------------------------------


@pytest.mark.skipif(trap_receiver.engine is None, reason="pysnmp not installed")
def test_usm_protocol_mapping_covers_all_names():
    for name in AUTH_PROTOCOLS:
        auth, _ = trap_receiver._usm_protocols(TrapV3User(user="u", auth_protocol=name))
        assert auth != trap_receiver.config.USM_AUTH_NONE
    for name in PRIV_PROTOCOLS:
        _, priv = trap_receiver._usm_protocols(TrapV3User(user="u", priv_protocol=name))
        assert priv != trap_receiver.config.USM_PRIV_NONE
    auth, priv = trap_receiver._usm_protocols(TrapV3User(user="u"))
    assert auth == trap_receiver.config.USM_AUTH_NONE
    assert priv == trap_receiver.config.USM_PRIV_NONE


@pytest.mark.skipif(trap_receiver.engine is None, reason="pysnmp not installed")
def test_register_v3_users_passes_mapped_args(monkeypatch):
    recorded: list[tuple] = []

    def _recorder(snmp_engine, user_name, **kwargs):
        recorded.append((user_name, kwargs))

    monkeypatch.setattr(trap_receiver.config, "add_v3_user", _recorder)

    receiver = trap_receiver.SNMPTrapReceiver(
        bind_port=10162,
        v3_users=[
            TrapV3User(**{**_FULL_USER}),  # type: ignore[arg-type]
            TrapV3User(user="inform-only", auth_protocol="SHA", auth_key="k" * 8),
        ],
    )
    receiver._register_v3_users(object())

    assert len(recorded) == 2
    name, kwargs = recorded[0]
    assert name == "nms-trap"
    assert kwargs["authProtocol"] == trap_receiver.config.USM_AUTH_HMAC192_SHA256
    assert kwargs["privProtocol"] == trap_receiver.config.USM_PRIV_CFB128_AES
    assert kwargs["authKey"] == "authpass123"
    assert kwargs["privKey"] == "privpass123"
    assert "securityEngineId" in kwargs

    name, kwargs = recorded[1]
    assert name == "inform-only"
    assert "securityEngineId" not in kwargs


@pytest.mark.skipif(trap_receiver.engine is None, reason="pysnmp not installed")
def test_register_v3_users_accepted_by_real_pysnmp():
    """Our kwargs must match the real config.add_v3_user signature."""
    snmp_engine = trap_receiver.engine.SnmpEngine()
    receiver = trap_receiver.SNMPTrapReceiver(
        bind_port=10162, v3_users=parse_trap_v3_users(json.dumps([_FULL_USER]))
    )
    receiver._register_v3_users(snmp_engine)  # must not raise
