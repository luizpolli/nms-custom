"""Well-known OID registry — symbolic name <-> numeric OID mapping.

Covers SNMPv2-MIB (system group), IF-MIB (interfaces), HOST-RESOURCES-MIB
(CPU/memory/storage), CISCO-PROCESS-MIB, CISCO-MEMORY-POOL-MIB and a handful
of trap OIDs used by alarm correlation.

Numeric OIDs are kept WITHOUT a leading dot (pysnmp/snmpwalk style).
"""

from __future__ import annotations

OID_REGISTRY: dict[str, str] = {
    # --- SNMPv2-MIB :: system group ---
    "sysDescr": "1.3.6.1.2.1.1.1.0",
    "sysObjectID": "1.3.6.1.2.1.1.2.0",
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "sysContact": "1.3.6.1.2.1.1.4.0",
    "sysName": "1.3.6.1.2.1.1.5.0",
    "sysLocation": "1.3.6.1.2.1.1.6.0",
    "sysServices": "1.3.6.1.2.1.1.7.0",

    # --- IF-MIB :: interfaces (table prefixes for snmpwalk) ---
    "ifNumber": "1.3.6.1.2.1.2.1.0",
    "ifIndex": "1.3.6.1.2.1.2.2.1.1",
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifType": "1.3.6.1.2.1.2.2.1.3",
    "ifMtu": "1.3.6.1.2.1.2.2.1.4",
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
    "ifPhysAddress": "1.3.6.1.2.1.2.2.1.6",
    "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
    "ifInUcastPkts": "1.3.6.1.2.1.2.2.1.11",
    "ifInErrors": "1.3.6.1.2.1.2.2.1.14",
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",
    "ifOutUcastPkts": "1.3.6.1.2.1.2.2.1.17",
    "ifOutErrors": "1.3.6.1.2.1.2.2.1.20",

    # --- IF-MIB high-capacity counters ---
    "ifHCInOctets": "1.3.6.1.2.1.31.1.1.1.6",
    "ifHCOutOctets": "1.3.6.1.2.1.31.1.1.1.10",
    "ifHighSpeed": "1.3.6.1.2.1.31.1.1.1.15",
    "ifAlias": "1.3.6.1.2.1.31.1.1.1.18",

    # --- HOST-RESOURCES-MIB ---
    "hrSystemUptime": "1.3.6.1.2.1.25.1.1.0",
    "hrProcessorLoad": "1.3.6.1.2.1.25.3.3.1.2",
    "hrStorageDescr": "1.3.6.1.2.1.25.2.3.1.3",
    "hrStorageSize": "1.3.6.1.2.1.25.2.3.1.5",
    "hrStorageUsed": "1.3.6.1.2.1.25.2.3.1.6",

    # --- CISCO-PROCESS-MIB :: CPU 1/5/15 min ---
    "cpmCPUTotal1minRev": "1.3.6.1.4.1.9.9.109.1.1.1.1.7",
    "cpmCPUTotal5minRev": "1.3.6.1.4.1.9.9.109.1.1.1.1.8",
    "cpmCPUTotal15minRev": "1.3.6.1.4.1.9.9.109.1.1.1.1.9",

    # --- CISCO-MEMORY-POOL-MIB ---
    "ciscoMemoryPoolUsed": "1.3.6.1.4.1.9.9.48.1.1.1.5",
    "ciscoMemoryPoolFree": "1.3.6.1.4.1.9.9.48.1.1.1.6",
    "ciscoMemoryPoolName": "1.3.6.1.4.1.9.9.48.1.1.1.2",

    # --- LLDP-MIB :: discovery (topology) ---
    "lldpRemSysName": "1.0.8802.1.1.2.1.4.1.1.9",
    "lldpRemPortId": "1.0.8802.1.1.2.1.4.1.1.7",
    "lldpRemPortDesc": "1.0.8802.1.1.2.1.4.1.1.8",
    "lldpRemChassisId": "1.0.8802.1.1.2.1.4.1.1.5",
    "lldpLocPortDesc": "1.0.8802.1.1.2.1.3.7.1.4",

    # --- CDP-MIB :: Cisco neighbor discovery ---
    "cdpCacheDeviceId": "1.3.6.1.4.1.9.9.23.1.2.1.1.6",
    "cdpCacheDevicePort": "1.3.6.1.4.1.9.9.23.1.2.1.1.7",
    "cdpCachePlatform": "1.3.6.1.4.1.9.9.23.1.2.1.1.8",
    "cdpCacheAddress": "1.3.6.1.4.1.9.9.23.1.2.1.1.4",

    # --- Common trap OIDs ---
    "snmpTrapOID": "1.3.6.1.6.3.1.1.4.1.0",
    "linkDown": "1.3.6.1.6.3.1.1.5.3",
    "linkUp": "1.3.6.1.6.3.1.1.5.4",
    "coldStart": "1.3.6.1.6.3.1.1.5.1",
    "warmStart": "1.3.6.1.6.3.1.1.5.2",
    "authenticationFailure": "1.3.6.1.6.3.1.1.5.5",
}

# Reverse map for OID-to-name lookups
_REVERSE: dict[str, str] = {v: k for k, v in OID_REGISTRY.items()}


def resolve_oid(name_or_oid: str) -> str:
    """Resolve a symbolic name (e.g. 'sysDescr') or numeric OID to numeric form.

    If ``name_or_oid`` is already numeric (starts with a digit) it is returned as-is
    (with any leading dot stripped). Otherwise, look it up in the registry.
    Raises KeyError if the symbolic name is not registered.
    """
    s = name_or_oid.lstrip(".")
    if not s:
        raise ValueError("Empty OID/name")
    if s[0].isdigit():
        return s
    if s not in OID_REGISTRY:
        raise KeyError(f"Unknown OID symbol: {name_or_oid!r}")
    return OID_REGISTRY[s]


def oid_name(numeric_oid: str) -> str | None:
    """Return the symbolic name for a numeric OID (exact match) or None.

    Falls back to a *prefix* match when the OID is a column under a known table
    OID — e.g. '1.3.6.1.2.1.2.2.1.2.5' returns 'ifDescr' (the table column),
    so callers can reason about row instances of a known column.
    """
    s = numeric_oid.lstrip(".")
    if s in _REVERSE:
        return _REVERSE[s]
    # Prefix match (longest wins)
    best: tuple[int, str] | None = None
    for oid, name in _REVERSE.items():
        if s.startswith(oid + "."):
            if best is None or len(oid) > best[0]:
                best = (len(oid), name)
    return best[1] if best else None
