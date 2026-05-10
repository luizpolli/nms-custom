"""Smoke tests for SNMP engine (no live device — tests pure logic only)."""

from app.services.snmp.oid_registry import OID_REGISTRY, oid_name, resolve_oid


def test_resolve_oid_symbolic() -> None:
    assert resolve_oid("sysDescr") == "1.3.6.1.2.1.1.1.0"


def test_resolve_oid_numeric_passthrough() -> None:
    assert resolve_oid("1.3.6.1.2.1.1.5.0") == "1.3.6.1.2.1.1.5.0"
    assert resolve_oid(".1.3.6.1.2.1.1.5.0") == "1.3.6.1.2.1.1.5.0"


def test_resolve_oid_unknown() -> None:
    import pytest
    with pytest.raises(KeyError):
        resolve_oid("notARealOid")


def test_oid_name_exact() -> None:
    assert oid_name("1.3.6.1.2.1.1.1.0") == "sysDescr"


def test_oid_name_prefix_match() -> None:
    # ifDescr table column → row instance
    assert oid_name("1.3.6.1.2.1.2.2.1.2.5") == "ifDescr"


def test_oid_name_unknown_returns_none() -> None:
    assert oid_name("9.9.9.9.9") is None


def test_registry_no_duplicate_oids() -> None:
    oids = list(OID_REGISTRY.values())
    assert len(oids) == len(set(oids)), "duplicate OIDs in registry"
