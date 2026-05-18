"""Cisco vendor SNMP trap fixtures for unit testing.

Each fixture is a dict with:
  - trap_oid: the snmpTrapOID value (OID string)
  - varbinds: dict of OID -> value (string representations as trap_receiver produces)
  - expected_event_type: normalized alarm category
  - expected_severity: one of critical/major/minor/warning/info/clear
  - expected_correlation_key_hint: OID key in varbinds that carries the correlation anchor

OIDs use numeric form without leading dot (matching trap_receiver.py style).
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# OID constants
# ---------------------------------------------------------------------------
_SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"
_SYS_UPTIME_OID = "1.3.6.1.2.1.1.3.0"
_SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"
_IF_INDEX = "1.3.6.1.2.1.2.2.1.1.1"

# Cisco BGP
_BGP_PEER2_STATE_CHANGED = "1.3.6.1.4.1.9.9.187.0.0.1"
_CBG_PEER2_REMOTE_ADDR = "1.3.6.1.4.1.9.9.187.1.2.5.1.11.0.0.0.0.1.192.168.100.2"
_CBG_PEER2_STATE = "1.3.6.1.4.1.9.9.187.1.2.5.1.3.0.0.0.0.1.192.168.100.2"
_CBG_PEER2_ADMIN_STATUS = "1.3.6.1.4.1.9.9.187.1.2.5.1.4.0.0.0.0.1.192.168.100.2"

# OSPF
_OSPF_NBR_STATE_CHANGE = "1.3.6.1.2.1.14.16.2.2"
_OSPF_NBR_IP_ADDR = "1.3.6.1.2.1.14.10.1.1.10.0.0.5.0"
_OSPF_NBR_STATE = "1.3.6.1.2.1.14.10.1.6.10.0.0.5.0"

# Cisco ENV MON - Fan
_CISCO_ENV_FAN_STATUS_CHANGE = "1.3.6.1.4.1.9.9.13.3.0.1"
_CISCO_ENV_FAN_STATUS_DESC = "1.3.6.1.4.1.9.9.13.1.4.1.2.1"
_CISCO_ENV_FAN_STATUS = "1.3.6.1.4.1.9.9.13.1.4.1.3.1"

# Cisco ENV MON - PSU
_CISCO_ENV_PSU_STATUS_CHANGE = "1.3.6.1.4.1.9.9.13.3.0.3"
_CISCO_ENV_PSU_DESC = "1.3.6.1.4.1.9.9.13.1.5.1.2.1"
_CISCO_ENV_PSU_STATE = "1.3.6.1.4.1.9.9.13.1.5.1.4.1"

# Cisco Config Change
_CCM_CLI_RUNNING_CONFIG_CHANGED = "1.3.6.1.4.1.9.9.43.2.0.2"
_CCM_HIST_EVENT_CMD_SRC = "1.3.6.1.4.1.9.9.43.1.1.6.1.5.1"
_CCM_HIST_EVENT_USER = "1.3.6.1.4.1.9.9.43.1.1.6.1.4.1"

# Standard link traps
_LINK_DOWN_OID = "1.3.6.1.6.3.1.1.5.3"
_LINK_UP_OID = "1.3.6.1.6.3.1.1.5.4"

# ---------------------------------------------------------------------------
# Fixture definitions
# ---------------------------------------------------------------------------

CISCO_TRAP_FIXTURES: list[dict[str, Any]] = [
    # --- linkDown (baseline coverage) ---
    {
        "name": "cisco_link_down",
        "trap_oid": _LINK_DOWN_OID,
        "varbinds": {
            _SYS_UPTIME_OID: "100",
            _SNMP_TRAP_OID: _LINK_DOWN_OID,
            _SYS_NAME_OID: "router-ncs55-1",
            _IF_INDEX: "2",
        },
        "expected_event_type": "link.down",
        "expected_severity": "major",
        "expected_correlation_key_hint": _IF_INDEX,
    },
    # --- linkUp (baseline coverage) ---
    {
        "name": "cisco_link_up",
        "trap_oid": _LINK_UP_OID,
        "varbinds": {
            _SYS_UPTIME_OID: "200",
            _SNMP_TRAP_OID: _LINK_UP_OID,
            _SYS_NAME_OID: "router-ncs55-1",
            _IF_INDEX: "2",
        },
        "expected_event_type": "link.up",
        "expected_severity": "clear",
        "expected_correlation_key_hint": _IF_INDEX,
    },
    # --- BGP peer state change ---
    {
        "name": "cisco_bgp_neighbor_state_change",
        "trap_oid": _BGP_PEER2_STATE_CHANGED,
        "varbinds": {
            _SYS_UPTIME_OID: "50000",
            _SNMP_TRAP_OID: _BGP_PEER2_STATE_CHANGED,
            _SYS_NAME_OID: "asr9k-pe1",
            _CBG_PEER2_REMOTE_ADDR: "192.168.100.2",
            _CBG_PEER2_STATE: "1",       # idle
            _CBG_PEER2_ADMIN_STATUS: "2",  # start
        },
        "expected_event_type": "bgp.neighbor_down",
        "expected_severity": "major",
        "expected_correlation_key_hint": _CBG_PEER2_REMOTE_ADDR,
    },
    # --- OSPF neighbor state change ---
    {
        "name": "cisco_ospf_nbr_state_change",
        "trap_oid": _OSPF_NBR_STATE_CHANGE,
        "varbinds": {
            _SYS_UPTIME_OID: "60000",
            _SNMP_TRAP_OID: _OSPF_NBR_STATE_CHANGE,
            _SYS_NAME_OID: "asr920-pe2",
            _OSPF_NBR_IP_ADDR: "10.0.0.5",
            _OSPF_NBR_STATE: "1",   # down
        },
        "expected_event_type": "ospf.neighbor_down",
        "expected_severity": "major",
        "expected_correlation_key_hint": _OSPF_NBR_IP_ADDR,
    },
    # --- Fan status change ---
    {
        "name": "cisco_entity_fan_status",
        "trap_oid": _CISCO_ENV_FAN_STATUS_CHANGE,
        "varbinds": {
            _SYS_UPTIME_OID: "70000",
            _SNMP_TRAP_OID: _CISCO_ENV_FAN_STATUS_CHANGE,
            _SYS_NAME_OID: "ncs560-pe3",
            _CISCO_ENV_FAN_STATUS_DESC: "FanTray0",
            _CISCO_ENV_FAN_STATUS: "3",   # failed
        },
        "expected_event_type": "environment.fan_fail",
        "expected_severity": "critical",
        "expected_correlation_key_hint": _CISCO_ENV_FAN_STATUS_DESC,
    },
    # --- PSU redundant supply status ---
    {
        "name": "cisco_entity_psu_status",
        "trap_oid": _CISCO_ENV_PSU_STATUS_CHANGE,
        "varbinds": {
            _SYS_UPTIME_OID: "80000",
            _SNMP_TRAP_OID: _CISCO_ENV_PSU_STATUS_CHANGE,
            _SYS_NAME_OID: "ncs560-pe3",
            _CISCO_ENV_PSU_DESC: "PowerSupply0",
            _CISCO_ENV_PSU_STATE: "4",   # notFunctioning
        },
        "expected_event_type": "environment.psu_fail",
        "expected_severity": "critical",
        "expected_correlation_key_hint": _CISCO_ENV_PSU_DESC,
    },
    # --- Config change ---
    {
        "name": "cisco_config_change",
        "trap_oid": _CCM_CLI_RUNNING_CONFIG_CHANGED,
        "varbinds": {
            _SYS_UPTIME_OID: "90000",
            _SNMP_TRAP_OID: _CCM_CLI_RUNNING_CONFIG_CHANGED,
            _SYS_NAME_OID: "asr9010-core1",
            _CCM_HIST_EVENT_USER: "admin",
            _CCM_HIST_EVENT_CMD_SRC: "1",   # commandLine
        },
        "expected_event_type": "config.change",
        "expected_severity": "warning",
        "expected_correlation_key_hint": _CCM_HIST_EVENT_USER,
    },
]
