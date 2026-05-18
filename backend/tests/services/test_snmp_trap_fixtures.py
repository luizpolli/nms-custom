"""Fixture-based tests for vendor SNMP trap classifier.

Phase 5L — Broader vendor SNMP trap fixtures.

Tests are split into two groups:

1. Parametrized classifier tests — drive the full fixture catalog through
   trap_classifier.classify_trap() and assert event_type, severity, and
   correlation_key extraction work for each Cisco trap variant.

2. End-to-end PDU round-trip test — feed the raw bytes produced by the
   simulator builders through the same varbind parsing logic the
   trap_receiver uses, then assert the classifier produces an alarm-shaped
   dict. No DB or event bus required (both are mocked).

NOTE: trap_receiver.SNMPTrapReceiver requires pysnmp-lextudio and a live
UDP socket, so the E2E test bypasses the class and calls the parsing logic
directly. If a full async integration test is needed in future (real socket),
that should live in a separate integration-test suite guarded by a marker.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make sure the backend package and the tools/ simulators are importable
# from the test runner's working directory.
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_ROOT = Path(__file__).resolve().parents[3] / "tools" / "simulators"
if str(_TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOLS_ROOT))

from app.services.snmp.trap_classifier import ClassifiedTrap, classify_trap
from tests.fixtures.traps.cisco_traps import CISCO_TRAP_FIXTURES


# ---------------------------------------------------------------------------
# 1. Parametrized classifier tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", CISCO_TRAP_FIXTURES, ids=[f["name"] for f in CISCO_TRAP_FIXTURES])
def test_classifier_event_type(fixture: dict) -> None:
    result: ClassifiedTrap = classify_trap(fixture["trap_oid"], fixture["varbinds"])
    assert result.event_type == fixture["expected_event_type"], (
        f"{fixture['name']}: expected event_type={fixture['expected_event_type']!r} "
        f"got {result.event_type!r}"
    )


@pytest.mark.parametrize("fixture", CISCO_TRAP_FIXTURES, ids=[f["name"] for f in CISCO_TRAP_FIXTURES])
def test_classifier_severity(fixture: dict) -> None:
    result: ClassifiedTrap = classify_trap(fixture["trap_oid"], fixture["varbinds"])
    assert result.severity == fixture["expected_severity"], (
        f"{fixture['name']}: expected severity={fixture['expected_severity']!r} "
        f"got {result.severity!r}"
    )


@pytest.mark.parametrize("fixture", CISCO_TRAP_FIXTURES, ids=[f["name"] for f in CISCO_TRAP_FIXTURES])
def test_classifier_correlation_key(fixture: dict) -> None:
    result: ClassifiedTrap = classify_trap(fixture["trap_oid"], fixture["varbinds"])
    hint_oid = fixture["expected_correlation_key_hint"]
    # The correlation_key value should match whatever is in varbinds at that OID
    expected_value = fixture["varbinds"].get(hint_oid)
    assert result.correlation_key == expected_value, (
        f"{fixture['name']}: expected correlation_key={expected_value!r} "
        f"got {result.correlation_key!r}"
    )


def test_classifier_unknown_oid_returns_generic() -> None:
    result = classify_trap("9.9.9.9.9.9", {})
    assert result.event_type == "snmp.trap"
    assert result.severity == "info"
    assert result.correlation_key is None


def test_classifier_none_oid_returns_generic() -> None:
    result = classify_trap(None, {"1.3.6.1.2.1.1.5.0": "router-1"})
    assert result.event_type == "snmp.trap"
    assert result.severity == "info"


# ---------------------------------------------------------------------------
# 2. Simulator round-trip: raw bytes -> parsed varbinds -> classifier
# ---------------------------------------------------------------------------

def _parse_ber_tlv(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """Minimal BER TLV decoder: returns (tag, value_bytes, next_offset)."""
    tag = data[offset]
    offset += 1
    length_byte = data[offset]
    offset += 1
    if length_byte & 0x80:
        num_bytes = length_byte & 0x7F
        length = int.from_bytes(data[offset:offset + num_bytes], "big")
        offset += num_bytes
    else:
        length = length_byte
    value = data[offset:offset + length]
    return tag, value, offset + length


def _parse_oid_value(raw: bytes) -> str:
    """Decode a BER-encoded OID value (without the TLV header)."""
    if not raw:
        return ""
    first = raw[0]
    parts = [first // 40, first % 40]
    idx = 1
    while idx < len(raw):
        val = 0
        while True:
            b = raw[idx]
            idx += 1
            val = (val << 7) | (b & 0x7F)
            if not (b & 0x80):
                break
        parts.append(val)
    return ".".join(str(p) for p in parts)


def _extract_varbinds_from_packet(packet: bytes) -> tuple[str | None, dict[str, str]]:
    """Walk a raw SNMPv2c Trap-PDU and return (trap_oid, varbinds_dict).

    This replicates the parsing path that pysnmp would produce inside
    trap_receiver._on_pysnmp_trap without depending on pysnmp.
    """
    # Outer SEQUENCE
    _, msg_val, _ = _parse_ber_tlv(packet, 0)
    offset = 0
    # Skip version integer
    tag, val, offset = _parse_ber_tlv(msg_val, offset)
    # Skip community string
    tag, val, offset = _parse_ber_tlv(msg_val, offset)
    # PDU (0xA7 = Trap-PDU)
    tag, pdu_val, offset = _parse_ber_tlv(msg_val, offset)
    # Skip request-id, error-status, error-index
    pdu_offset = 0
    for _ in range(3):
        _, _, pdu_offset = _parse_ber_tlv(pdu_val, pdu_offset)
    # VarBindList SEQUENCE
    _, vbl_val, _ = _parse_ber_tlv(pdu_val, pdu_offset)
    # Each VarBind is a SEQUENCE of OID + value
    varbinds: dict[str, str] = {}
    trap_oid: str | None = None
    vb_offset = 0
    while vb_offset < len(vbl_val):
        _, vb_val, vb_offset = _parse_ber_tlv(vbl_val, vb_offset)
        vb_inner = 0
        oid_tag, oid_raw, vb_inner = _parse_ber_tlv(vb_val, vb_inner)
        val_tag, val_raw, _ = _parse_ber_tlv(vb_val, vb_inner)
        oid_str = _parse_oid_value(oid_raw)
        # Decode value to string (integers and strings only)
        if val_tag in (0x02, 0x43):  # INTEGER or TimeTicks
            val_str = str(int.from_bytes(val_raw, "big")) if val_raw else "0"
        elif val_tag == 0x04:  # OCTET STRING
            val_str = val_raw.decode("utf-8", errors="replace")
        elif val_tag == 0x06:  # OID
            val_str = _parse_oid_value(val_raw)
        else:
            val_str = val_raw.hex()
        varbinds[oid_str] = val_str
        if oid_str == "1.3.6.1.6.3.1.1.4.1.0":
            trap_oid = val_str
    return trap_oid, varbinds


@pytest.mark.parametrize(
    "trap_type,expected_event_type,expected_severity",
    [
        ("link-down", "link.down", "major"),
        ("link-up", "link.up", "clear"),
        ("bgp-down", "bgp.neighbor_down", "major"),
        ("ospf-down", "ospf.neighbor_down", "major"),
        ("fan-fail", "environment.fan_fail", "critical"),
        ("psu-fail", "environment.psu_fail", "critical"),
        ("config-change", "config.change", "warning"),
    ],
)
def test_simulator_packet_round_trip(
    trap_type: str, expected_event_type: str, expected_severity: str
) -> None:
    """Build a raw PDU via the simulator, parse varbinds, classify — assert alarm shape."""
    from mock_device import MockDevice, build_snmp_v2c_trap_packet  # type: ignore[import]

    device = MockDevice(name="test-router-1", ip_address="10.255.0.11")
    packet = build_snmp_v2c_trap_packet(device, sequence=1, community="public", trap_type=trap_type)
    assert isinstance(packet, bytes)
    assert len(packet) > 10

    trap_oid, varbinds = _extract_varbinds_from_packet(packet)
    result = classify_trap(trap_oid, varbinds)

    assert result.event_type == expected_event_type, (
        f"trap_type={trap_type!r}: expected {expected_event_type!r} got {result.event_type!r}"
    )
    assert result.severity == expected_severity, (
        f"trap_type={trap_type!r}: expected {expected_severity!r} got {result.severity!r}"
    )
    # Alarm-shaped dict check
    alarm = {
        "event_type": result.event_type,
        "severity": result.severity,
        "correlation_key": result.correlation_key,
        "trap_oid": result.trap_oid,
        "raw_varbinds": result.raw_varbinds,
    }
    assert alarm["event_type"]
    assert alarm["severity"]
    assert alarm["trap_oid"]
