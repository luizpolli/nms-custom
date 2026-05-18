"""Data-driven SNMP trap OID classifier.

Maps known Cisco (IOS XR / IOS XE / NX-OS) trap OIDs to normalized event
metadata. Unknown OIDs fall back to a generic shape so the caller can still
produce an alarm record.

Public API
----------
classify_trap(trap_oid, varbinds) -> ClassifiedTrap
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# OID prefix for correlation-key extraction (most important varbind OID per
# trap type).  These are *prefix* matches: the first varbind whose OID starts
# with the hint prefix is used as the correlation anchor value.
# ---------------------------------------------------------------------------
_TRAP_MAP: dict[str, dict[str, Any]] = {
    # Standard link traps (RFC 2863)
    "1.3.6.1.6.3.1.1.5.3": {
        "event_type": "link.down",
        "severity": "major",
        "correlation_key_prefix": "1.3.6.1.2.1.2.2.1.1",  # ifIndex
    },
    "1.3.6.1.6.3.1.1.5.4": {
        "event_type": "link.up",
        "severity": "clear",
        "correlation_key_prefix": "1.3.6.1.2.1.2.2.1.1",  # ifIndex
    },
    # Cisco BGP MIB v2 — cbgpPeer2StateChanged
    "1.3.6.1.4.1.9.9.187.0.0.1": {
        "event_type": "bgp.neighbor_down",
        "severity": "major",
        "correlation_key_prefix": "1.3.6.1.4.1.9.9.187.1.2.5.1.11",  # cbgpPeer2RemoteAddr
    },
    # OSPF-MIB — ospfNbrStateChange
    "1.3.6.1.2.1.14.16.2.2": {
        "event_type": "ospf.neighbor_down",
        "severity": "major",
        "correlation_key_prefix": "1.3.6.1.2.1.14.10.1.1",  # ospfNbrIpAddr
    },
    # Cisco ENV MON MIB — fan status change
    "1.3.6.1.4.1.9.9.13.3.0.1": {
        "event_type": "environment.fan_fail",
        "severity": "critical",
        "correlation_key_prefix": "1.3.6.1.4.1.9.9.13.1.4.1.2",  # ciscoEnvMonFanStatusDescr
    },
    # Cisco ENV MON MIB — redundant PSU supply
    "1.3.6.1.4.1.9.9.13.3.0.3": {
        "event_type": "environment.psu_fail",
        "severity": "critical",
        "correlation_key_prefix": "1.3.6.1.4.1.9.9.13.1.5.1.2",  # ciscoEnvMonSupplyStatusDescr
    },
    # Cisco Config Man MIB — ccmCLIRunningConfigChanged
    "1.3.6.1.4.1.9.9.43.2.0.2": {
        "event_type": "config.change",
        "severity": "warning",
        "correlation_key_prefix": "1.3.6.1.4.1.9.9.43.1.1.6.1.4",  # ccmHistoryEventUser
    },
}

_GENERIC: dict[str, Any] = {
    "event_type": "snmp.trap",
    "severity": "info",
    "correlation_key_prefix": None,
}


@dataclass(slots=True)
class ClassifiedTrap:
    """Result of OID classification."""

    trap_oid: str
    event_type: str
    severity: str
    correlation_key: str | None  # value extracted from varbinds, or None
    raw_varbinds: dict[str, str]


def classify_trap(trap_oid: str | None, varbinds: dict[str, str]) -> ClassifiedTrap:
    """Classify a received trap by OID and extract the correlation key.

    Falls back to generic shape when the OID is unknown.
    """
    oid = (trap_oid or "").lstrip(".")
    meta = _TRAP_MAP.get(oid, _GENERIC)
    correlation_key = _extract_correlation_key(varbinds, meta["correlation_key_prefix"])
    return ClassifiedTrap(
        trap_oid=oid,
        event_type=meta["event_type"],
        severity=meta["severity"],
        correlation_key=correlation_key,
        raw_varbinds=dict(varbinds),
    )


def _extract_correlation_key(varbinds: dict[str, str], prefix: str | None) -> str | None:
    if prefix is None:
        return None
    for oid, value in varbinds.items():
        if oid.startswith(prefix):
            return value
    return None
