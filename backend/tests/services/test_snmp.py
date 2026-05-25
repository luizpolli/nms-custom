"""Smoke tests for SNMP engine (no live device — tests pure logic only)."""

import pytest

from app.services.snmp.engine import SNMPEngine
from app.services.snmp.oid_registry import OID_REGISTRY, oid_name, resolve_oid
from app.services.snmp.poller import SNMPCredential, SNMPResult


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


@pytest.mark.asyncio
async def test_get_physical_inventory_maps_entity_mib_rows() -> None:
    class FakePoller:
        async def bulk_walk(self, host: str, oid: str, cred: SNMPCredential) -> SNMPResult:
            del cred
            values = {
                OID_REGISTRY["entPhysicalName"]: {f"{oid}.100": "module 0/RSP0"},
                OID_REGISTRY["entPhysicalSerialNum"]: {f"{oid}.100": "FOC1234ABCD"},
                OID_REGISTRY["entPhysicalContainedIn"]: {f"{oid}.100": "1"},
                OID_REGISTRY["entPhysicalIsFRU"]: {f"{oid}.100": "true"},
            }
            return SNMPResult(host=host, success=True, varbinds=values.get(oid, {}))

    engine = object.__new__(SNMPEngine)
    engine.poller = FakePoller()

    rows = await engine.get_physical_inventory("10.0.0.1", SNMPCredential())

    assert rows[100].name == "module 0/RSP0"
    assert rows[100].serial_number == "FOC1234ABCD"
    assert rows[100].contained_in == 1
    assert rows[100].is_fru is True
    assert rows[100].to_chassis_inventory()["physicalIndex"] == 100
