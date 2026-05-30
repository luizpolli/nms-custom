#!/usr/bin/env python3
"""
Sanitize and enrich NCS540-16Z4 SNMP walk data.

Tasks:
1. Sanitize 4 raw NCS540-16Z4 walks (strip hostnames, serial numbers, IPs from ifAlias)
2. Enrich chassis profile with real component data from entity-mib normalized JSON
3. Wire sensor/FRU data to chassis view (temperature, voltage, rpm, PSU status)
4. Mask real serial numbers in chassis profile with REDACTED placeholders
"""

import re
import json
import copy
from pathlib import Path
from datetime import datetime, timezone

REPO = Path(__file__).parent.parent.parent
WALKS_DIR = REPO / "docs/snmpwalks"
SANITIZED_DIR = WALKS_DIR / "sanitized"
NORMALIZED_DIR = WALKS_DIR / "normalized"
CHASSIS_PROFILE = REPO / "frontend/public/chassis-assets/ncs540-16z4/normalized.json"

# ─────────────────────────────────────────────────────────────────────────────
# PART 1: Sanitize raw walks
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_ifAlias(value: str, counter: list) -> str:
    """Replace ifAlias values that contain real hostnames/identifiers."""
    # Keep generic descriptions that don't reveal topology
    generic_patterns = [
        r'^Routing\s*$',
        r'^Management\s*$',
        r'^$',
    ]
    for pat in generic_patterns:
        if re.match(pat, value.strip()):
            return value  # keep as-is

    # Replace anything that looks like a real device hostname or circuit description
    counter[0] += 1
    n = counter[0]
    return f"TEST-LINK-NCS540-16Z4-{n:04d}"


def sanitize_walk(src_path: Path, dst_path: Path, walk_type: str) -> dict:
    """Sanitize a single walk file. Returns stats dict."""
    stats = {"ifAlias_lines": 0, "serial_lines": 0, "ip_values": 0}
    alias_counter = [0]
    lines_out = []

    with open(src_path) as f:
        lines = f.readlines()

    for line in lines:
        # ── ifAlias replacements (only in ifXTable) ──────────────────────────
        if walk_type == "ifXTable":
            m = re.match(r'(IF-MIB::ifAlias\.\d+\s+=\s+STRING:\s*)(.*)', line)
            if m:
                prefix, alias_val = m.group(1), m.group(2).rstrip('\n')
                sanitized = sanitize_ifAlias(alias_val, alias_counter)
                if sanitized != alias_val:
                    stats["ifAlias_lines"] += 1
                lines_out.append(f"{prefix}{sanitized}\n")
                continue

        # ── IP address replacements (only in STRING values, not OID paths) ───
        # Match IP addresses only in the value portion (after '= STRING: ' or '= IpAddress: ')
        ip_in_value = re.match(
            r'(.*=\s+(?:STRING|IpAddress):\s*)([^\n]*)',
            line
        )
        if ip_in_value:
            prefix_val = ip_in_value.group(1)
            value_part = ip_in_value.group(2)
            ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
            if re.search(ip_pattern, value_part):
                new_value = re.sub(ip_pattern, '192.0.2.0', value_part)
                line = prefix_val + new_value + '\n'
                stats["ip_values"] += 1

        lines_out.append(line)

    dst_path.write_text(''.join(lines_out))
    return stats


def sanitize_all_walks():
    """Sanitize all 4 raw 16Z4 walks."""
    files = {
        "ciscoEntitySensorNCS540-16Z4.walk": "sensor",
        "ciscoEntityFRUControlNCS540-16Z4.walk": "fru",
        "ifXTableNCS540-16Z4.walk": "ifXTable",
        "interfacesNCS540-16Z4.walk": "interfaces",
    }
    report = {}
    for fname, wtype in files.items():
        src = WALKS_DIR / fname
        dst = SANITIZED_DIR / fname
        if not src.exists():
            print(f"WARNING: {src} not found, skipping")
            continue
        stats = sanitize_walk(src, dst, wtype)
        report[fname] = stats
        print(f"  Sanitized {fname}: {stats}")
    return report


# ─────────────────────────────────────────────────────────────────────────────
# PART 2: Parse sensor walk
# ─────────────────────────────────────────────────────────────────────────────

SENSOR_TYPES = {
    1: 'other', 2: 'unknown', 3: 'voltsDC', 4: 'voltsAC', 5: 'amperes',
    6: 'watts', 7: 'hertz', 8: 'celsius', 9: 'percentRH', 10: 'rpm',
    11: 'cmm', 12: 'truthvalue', 13: 'specialEnum', 14: 'dBm'
}
SENSOR_SCALES = {
    1: 'yocto', 2: 'zepto', 3: 'atto', 4: 'femto', 5: 'pico',
    6: 'nano', 7: 'micro', 8: 'milli', 9: 'units', 10: 'kilo',
    11: 'mega', 12: 'giga', 13: 'tera', 14: 'exa', 15: 'peta',
    16: 'zetta', 17: 'yotta'
}
SCALE_MULTIPLIERS = {
    6: 1e-9, 7: 1e-6, 8: 1e-3, 9: 1.0, 10: 1e3, 11: 1e6
}


def parse_sensor_walk(walk_path: Path) -> dict:
    """
    Parse CISCO-ENTITY-SENSOR-MIB walk.
    Returns dict keyed by physicalIndex with sensor readings.
    """
    raw = {}  # {physicalIndex: {field: value}}

    with open(walk_path) as f:
        for line in f:
            # Integer fields: .field.index = INTEGER: value
            m = re.match(
                r'SNMPv2-SMI::enterprises\.9\.9\.91\.1\.1\.1\.1\.(\d+)\.(\d+)'
                r'\s+=\s+INTEGER:\s+(-?\d+)',
                line
            )
            if m:
                field, idx, val = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if idx not in raw:
                    raw[idx] = {}
                raw[idx][field] = val

            # String field (units display) - field 6
            m2 = re.match(
                r'SNMPv2-SMI::enterprises\.9\.9\.91\.1\.1\.1\.1\.6\.(\d+)'
                r'\s+=\s+STRING:\s+"?([^"]*)"?',
                line
            )
            if m2:
                idx2 = int(m2.group(1))
                if idx2 not in raw:
                    raw[idx2] = {}
                raw[idx2]['units_display'] = m2.group(2).strip()

    # Build structured sensor info
    sensors = {}
    for idx, d in raw.items():
        stype_id = d.get(1, 0)
        scale_id = d.get(2, 9)
        precision = d.get(3, 0)
        raw_value = d.get(4, 0)
        oper_status = d.get(5, 1)

        scale_mult = SCALE_MULTIPLIERS.get(scale_id, 1.0)
        actual_value = raw_value * scale_mult
        if precision > 0:
            actual_value = round(actual_value, precision)

        sensors[idx] = {
            'sensorType': SENSOR_TYPES.get(stype_id, 'unknown'),
            'sensorTypeId': stype_id,
            'scale': SENSOR_SCALES.get(scale_id, 'units'),
            'scaleId': scale_id,
            'precision': precision,
            'rawValue': raw_value,
            'value': actual_value,
            'operStatus': oper_status,
            'operStatusLabel': {1: 'ok', 2: 'unavailable', 3: 'nonoperational'}.get(oper_status, 'unknown'),
            'unitsDisplay': d.get('units_display', ''),
        }

    return sensors


# ─────────────────────────────────────────────────────────────────────────────
# PART 3: Parse FRU walk
# ─────────────────────────────────────────────────────────────────────────────

def parse_fru_walk(walk_path: Path) -> dict:
    """
    Parse CISCO-ENTITY-FRU-CONTROL-MIB walk.
    Returns dict keyed by physicalIndex with FRU power status.
    """
    # CISCO-ENTITY-FRU-CONTROL-MIB OID mapping:
    # .9.9.117.1.1.2.1.1 = cefcFRUPowerAdminStatus (1=on, 2=off, 3=inlineAuto, 4=inlineOn, 5=powerCycle)
    # .9.9.117.1.1.2.1.2 = cefcFRUPowerOperStatus  (1=off, 2=on, 3=fanFailed, 4=onButFanFailed,
    #                                                5=partiallyOn, 6=failed, 7=communicating, 8=notApplicable)
    # .9.9.117.1.1.2.1.3 = cefcFRUCurrent (milliamps)
    # .9.9.117.1.5.1.1.1 = cefcFRUPresent (1=false, 2=true)

    raw = {}
    with open(walk_path) as f:
        for line in f:
            m = re.match(
                r'SNMPv2-SMI::enterprises\.9\.9\.117\.1\.1\.2\.1\.(\d+)\.(\d+)'
                r'\s+=\s+INTEGER:\s+(\d+)',
                line
            )
            if m:
                field, idx, val = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if idx not in raw:
                    raw[idx] = {}
                raw[idx][f'power_{field}'] = val

            # cefcFRUPresent
            m2 = re.match(
                r'SNMPv2-SMI::enterprises\.9\.9\.117\.1\.5\.1\.1\.1\.(\d+)'
                r'\s+=\s+INTEGER:\s+(\d+)',
                line
            )
            if m2:
                idx2, val2 = int(m2.group(1)), int(m2.group(2))
                if idx2 not in raw:
                    raw[idx2] = {}
                raw[idx2]['present'] = val2

    admin_labels = {1: 'on', 2: 'off', 3: 'inlineAuto', 4: 'inlineOn', 5: 'powerCycle'}
    # cefcFRUPowerOperStatus (CISCO-ENTITY-FRU-CONTROL-MIB)
    oper_labels = {
        1: 'offEnvOther', 2: 'on', 3: 'offAdmin', 4: 'offDenied',
        5: 'offEnvPower', 6: 'offEnvTemp', 7: 'offEnvFan', 8: 'failed',
        9: 'onButFanFail', 10: 'offCooling', 11: 'offConnectorRating', 12: 'onButInlinePowerFail'
    }

    fru = {}
    for idx, d in raw.items():
        admin_id = d.get('power_1', 1)
        oper_id = d.get('power_2', 2)
        current_ma = d.get('power_3', 0)
        present_id = d.get('present', 2)

        fru[idx] = {
            'adminStatus': admin_labels.get(admin_id, 'unknown'),
            'adminStatusId': admin_id,
            'operStatus': oper_labels.get(oper_id, 'unknown'),
            'operStatusId': oper_id,
            'currentMilliAmps': current_ma,
            'present': present_id == 2,
        }

    return fru


# ─────────────────────────────────────────────────────────────────────────────
# PART 4: Enrich chassis profile
# ─────────────────────────────────────────────────────────────────────────────

# Serial number mapping: real → redacted placeholder
# We keep deterministic placeholders so repeated builds are stable
SERIAL_REDACTIONS = {
    "FOC2634PCJ6":  "REDACTED-NCS540-RP-0001",
    "FOC2634P0G1":  "REDACTED-NCS540-FAN-0001",
    "FOC2636NR42":  "REDACTED-NCS540-CHASSIS-0001",
    "MTC22520WTV":  "REDACTED-SFP-GE-0001",
    "MTC230305AB":  "REDACTED-SFP-GE-0002",
    "AN131800CY":   "REDACTED-SFP-GE-0003",
    "ONT1842008V":  "REDACTED-SFP-10G-0001",
    "ONT210300RK":  "REDACTED-SFP-10G-0002",
    "ACW262603ZK":  "REDACTED-SFP-10G-0003",
    "OPM26280RFZ":  "REDACTED-SFP-10G-0004",
    "FBN2910K05S":  "REDACTED-QSFP-100G-0001",
}


def enrich_chassis_profile(sensors: dict, fru: dict):
    """
    Enrich the NCS540-16Z4 chassis profile:
    1. Replace real serial numbers with REDACTED placeholders
    2. Add sensor readings (temp, voltage, current, optical) to sensor components
    3. Add FRU power status to FRUable components (PSU, fan, modules)
    4. Update generatedAt timestamp
    """
    with open(CHASSIS_PROFILE) as f:
        profile = json.load(f)

    updated_serials = 0
    updated_sensors = 0
    updated_fru = 0

    for comp_id, comp in profile['componentsById'].items():
        # ── 1. Redact real serial numbers ────────────────────────────────────
        serial = comp.get('serialNumber', '')
        if serial and serial not in ('N/A', '', 'REDACTED') and serial in SERIAL_REDACTIONS:
            comp['serialNumber'] = SERIAL_REDACTIONS[serial]
            updated_serials += 1

        phys_idx = comp.get('physicalIndex')
        if phys_idx is None:
            continue

        # ── 2. Wire sensor readings to sensor-type components ─────────────────
        if comp.get('type') == 'sensor' and phys_idx in sensors:
            s = sensors[phys_idx]
            comp['sensor'] = {
                'sensorType':    s['sensorType'],
                'scale':         s['scale'],
                'value':         s['value'],
                'rawValue':      s['rawValue'],
                'operStatus':    s['operStatusLabel'],
                'unitsDisplay':  s['unitsDisplay'],
            }
            updated_sensors += 1

        # ── 3. Wire FRU power status to FRUable components ────────────────────
        if comp.get('isFRUable') == 1 and phys_idx in fru:
            f_data = fru[phys_idx]
            comp['fru'] = {
                'adminStatus':      f_data['adminStatus'],
                'operStatus':       f_data['operStatus'],
                'present':          f_data['present'],
                'currentMilliAmps': f_data['currentMilliAmps'],
            }
            updated_fru += 1

    # ── 4. Update metadata ────────────────────────────────────────────────────
    profile['generatedAt'] = datetime.now(timezone.utc).isoformat()
    profile['source']['sensorDataSource'] = 'docs/snmpwalks/sanitized/ciscoEntitySensorNCS540-16Z4.walk'
    profile['source']['fruDataSource'] = 'docs/snmpwalks/sanitized/ciscoEntityFRUControlNCS540-16Z4.walk'
    profile['source']['enrichedAt'] = datetime.now(timezone.utc).isoformat()

    with open(CHASSIS_PROFILE, 'w') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print(f"  Chassis profile updated:")
    print(f"    Serials redacted:    {updated_serials}")
    print(f"    Sensors enriched:    {updated_sensors}")
    print(f"    FRU status applied:  {updated_fru}")
    return updated_serials, updated_sensors, updated_fru


# ─────────────────────────────────────────────────────────────────────────────
# PART 5: Update sanitization report
# ─────────────────────────────────────────────────────────────────────────────

def update_sanitization_report(walk_stats: dict):
    """Append 16Z4 entries to the existing sanitization report."""
    report_path = SANITIZED_DIR / "SANITIZATION_REPORT.json"
    with open(report_path) as f:
        report = json.load(f)

    for fname, stats in walk_stats.items():
        report['by_file'][fname] = {
            'serial_lines': stats.get('serial_lines', 0),
            'ifAlias_lines': stats.get('ifAlias_lines', 0),
            'ip_values': stats.get('ip_values', 0),
        }
        report['sanitization']['ifAlias_lines_replaced'] += stats.get('ifAlias_lines', 0)
        report['sanitization']['ip_address_values_replaced'] += stats.get('ip_values', 0)

    report['files'] += len(walk_stats)

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=4)

    print(f"  Updated SANITIZATION_REPORT.json")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("NCS540-16Z4 Walk Sanitization & Chassis Enrichment")
    print("=" * 60)

    print("\n[1/4] Sanitizing raw walks...")
    walk_stats = sanitize_all_walks()

    print("\n[2/4] Parsing sensor walk...")
    sensor_walk_path = WALKS_DIR / "ciscoEntitySensorNCS540-16Z4.walk"
    sensors = parse_sensor_walk(sensor_walk_path)
    print(f"  Parsed {len(sensors)} sensor entries")
    # Summary by type
    type_counts = {}
    for s in sensors.values():
        t = s['sensorType']
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")

    print("\n[3/4] Parsing FRU walk...")
    fru_walk_path = WALKS_DIR / "ciscoEntityFRUControlNCS540-16Z4.walk"
    fru = parse_fru_walk(fru_walk_path)
    print(f"  Parsed {len(fru)} FRU entries")
    # Summary by oper status
    oper_counts = {}
    for fi in fru.values():
        o = fi['operStatus']
        oper_counts[o] = oper_counts.get(o, 0) + 1
    for o, c in sorted(oper_counts.items()):
        print(f"    {o}: {c}")

    print("\n[4/4] Enriching chassis profile...")
    enrich_chassis_profile(sensors, fru)

    print("\n[+] Updating sanitization report...")
    update_sanitization_report(walk_stats)

    print("\n✓ Done!")
