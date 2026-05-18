#!/usr/bin/env python3
"""Mock device traffic generator for local NMS_Custom labs.

Generates Cisco-ish syslog messages and line-delimited gNMI/MDT JSON telemetry
frames against the local receivers. It can also create/find a mock inventory
Device through the API so telemetry samples satisfy FK constraints.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

LINK_DOWN_OID = "1.3.6.1.6.3.1.1.5.3"
LINK_UP_OID = "1.3.6.1.6.3.1.1.5.4"
SYS_UPTIME_OID = "1.3.6.1.2.1.1.3.0"
SYS_NAME_OID = "1.3.6.1.2.1.1.5.0"
SNMP_TRAP_OID = "1.3.6.1.6.3.1.1.4.1.0"
IF_INDEX_PREFIX = "1.3.6.1.2.1.2.2.1.1"

# Cisco vendor trap OIDs
BGP_PEER2_STATE_CHANGED = "1.3.6.1.4.1.9.9.187.0.0.1"
OSPF_NBR_STATE_CHANGE = "1.3.6.1.2.1.14.16.2.2"
CISCO_ENV_FAN_STATUS_CHANGE = "1.3.6.1.4.1.9.9.13.3.0.1"
CISCO_ENV_PSU_STATUS_CHANGE = "1.3.6.1.4.1.9.9.13.3.0.3"
CCM_CLI_RUNNING_CONFIG_CHANGED = "1.3.6.1.4.1.9.9.43.2.0.2"

VALID_TRAP_TYPES = ("link-down", "link-up", "bgp-down", "ospf-down", "fan-fail", "psu-fail", "config-change")


@dataclass(slots=True)
class MockDevice:
    name: str = "mock-iosxr-1"
    ip_address: str = "10.255.0.11"
    platform: str = "IOS XRv 9000"
    site: str = "lab"


def build_syslog_message(device: MockDevice, sequence: int, *, alarm: bool = False) -> str:
    """Build a Cisco-ish BSD syslog payload."""
    if alarm:
        return (
            f"<131>{datetime.now(timezone.utc).strftime('%b %d %H:%M:%S')} {device.name} "
            f"%LINK-3-UPDOWN: Interface GigabitEthernet0/0/0/{sequence % 4} changed state to down"
        )
    return (
        f"<134>{datetime.now(timezone.utc).strftime('%b %d %H:%M:%S')} {device.name} "
        f"%NMS-6-MOCK: mock heartbeat sequence={sequence} platform={device.platform}"
    )


def _ber_length(length: int) -> bytes:
    if length < 0x80:
        return bytes([length])
    raw = length.to_bytes((length.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(raw)]) + raw


def _ber_tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _ber_length(len(value)) + value


def _ber_sequence(value: bytes) -> bytes:
    return _ber_tlv(0x30, value)


def _ber_integer(value: int, *, tag: int = 0x02) -> bytes:
    if value == 0:
        raw = b"\x00"
    else:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        if raw[0] & 0x80:
            raw = b"\x00" + raw
    return _ber_tlv(tag, raw)


def _ber_octet_string(value: str) -> bytes:
    return _ber_tlv(0x04, value.encode("utf-8"))


def _ber_oid(oid: str) -> bytes:
    parts = [int(part) for part in oid.strip(".").split(".")]
    if len(parts) < 2:
        raise ValueError(f"OID requires at least two arcs: {oid!r}")
    encoded = bytearray([40 * parts[0] + parts[1]])
    for part in parts[2:]:
        if part < 0:
            raise ValueError(f"OID arc must be positive: {oid!r}")
        stack = [part & 0x7F]
        part >>= 7
        while part:
            stack.append(0x80 | (part & 0x7F))
            part >>= 7
        encoded.extend(reversed(stack))
    return _ber_tlv(0x06, bytes(encoded))


def _ber_varbind(oid: str, value: bytes) -> bytes:
    return _ber_sequence(_ber_oid(oid) + value)


def _build_pdu(community: str, sequence: int, varbind_bytes: bytes) -> bytes:
    """Wrap varbinds into a full SNMPv2c Trap-PDU (SEQUENCE wrapper)."""
    varbinds = _ber_sequence(varbind_bytes)
    pdu = _ber_tlv(0xA7, _ber_integer(sequence) + _ber_integer(0) + _ber_integer(0) + varbinds)
    return _ber_sequence(_ber_integer(1) + _ber_octet_string(community) + pdu)


def _common_varbinds(device: MockDevice, trap_oid: str, sequence: int) -> bytes:
    uptime_ticks = max(1, sequence) * 100
    return (
        _ber_varbind(SYS_UPTIME_OID, _ber_integer(uptime_ticks, tag=0x43))
        + _ber_varbind(SNMP_TRAP_OID, _ber_oid(trap_oid))
        + _ber_varbind(SYS_NAME_OID, _ber_octet_string(device.name))
    )


def build_snmp_v2c_trap_packet(
    device: MockDevice,
    sequence: int,
    *,
    community: str = "public",
    trap_type: str = "link-down",
) -> bytes:
    """Build a minimal SNMPv2c Trap-PDU without requiring pysnmp locally.

    trap_type accepts: link-down, link-up, bgp-down, ospf-down, fan-fail,
    psu-fail, config-change.
    """
    builders = {
        "link-down": _build_link_down,
        "link-up": _build_link_up,
        "bgp-down": _build_bgp_down,
        "ospf-down": _build_ospf_down,
        "fan-fail": _build_fan_fail,
        "psu-fail": _build_psu_fail,
        "config-change": _build_config_change,
    }
    if trap_type not in builders:
        raise ValueError(f"Unknown trap_type {trap_type!r}. Valid: {list(builders)}")
    varbind_bytes = builders[trap_type](device, sequence)
    return _build_pdu(community, sequence, varbind_bytes)


def _build_link_down(device: MockDevice, sequence: int) -> bytes:
    if_index = ((sequence - 1) // 2) % 4 + 1
    return (
        _common_varbinds(device, LINK_DOWN_OID, sequence)
        + _ber_varbind(f"{IF_INDEX_PREFIX}.{if_index}", _ber_integer(if_index))
    )


def _build_link_up(device: MockDevice, sequence: int) -> bytes:
    if_index = ((sequence - 1) // 2) % 4 + 1
    return (
        _common_varbinds(device, LINK_UP_OID, sequence)
        + _ber_varbind(f"{IF_INDEX_PREFIX}.{if_index}", _ber_integer(if_index))
    )


def _build_bgp_down(device: MockDevice, sequence: int) -> bytes:
    peer_ip = f"192.168.{sequence % 256}.{(sequence % 254) + 1}"
    peer_oid_suffix = ".".join(str(o) for o in [0, 0, 0, 0, 1] + [int(x) for x in peer_ip.split(".")])
    remote_addr_oid = f"1.3.6.1.4.1.9.9.187.1.2.5.1.11.{peer_oid_suffix}"
    peer_state_oid = f"1.3.6.1.4.1.9.9.187.1.2.5.1.3.{peer_oid_suffix}"
    return (
        _common_varbinds(device, BGP_PEER2_STATE_CHANGED, sequence)
        + _ber_varbind(remote_addr_oid, _ber_octet_string(peer_ip))
        + _ber_varbind(peer_state_oid, _ber_integer(1))  # idle
    )


def _build_ospf_down(device: MockDevice, sequence: int) -> bytes:
    nbr_ip = f"10.0.{sequence % 256}.{(sequence % 254) + 1}"
    nbr_ip_oid = "1.3.6.1.2.1.14.10.1.1." + ".".join(str(o) for o in [int(x) for x in nbr_ip.split(".")] + [0])
    nbr_state_oid = "1.3.6.1.2.1.14.10.1.6." + ".".join(str(o) for o in [int(x) for x in nbr_ip.split(".")] + [0])
    return (
        _common_varbinds(device, OSPF_NBR_STATE_CHANGE, sequence)
        + _ber_varbind(nbr_ip_oid, _ber_octet_string(nbr_ip))
        + _ber_varbind(nbr_state_oid, _ber_integer(1))  # down
    )


def _build_fan_fail(device: MockDevice, sequence: int) -> bytes:
    fan_idx = (sequence % 4) + 1
    descr_oid = f"1.3.6.1.4.1.9.9.13.1.4.1.2.{fan_idx}"
    status_oid = f"1.3.6.1.4.1.9.9.13.1.4.1.3.{fan_idx}"
    return (
        _common_varbinds(device, CISCO_ENV_FAN_STATUS_CHANGE, sequence)
        + _ber_varbind(descr_oid, _ber_octet_string(f"FanTray{fan_idx - 1}"))
        + _ber_varbind(status_oid, _ber_integer(3))  # failed
    )


def _build_psu_fail(device: MockDevice, sequence: int) -> bytes:
    psu_idx = (sequence % 2) + 1
    descr_oid = f"1.3.6.1.4.1.9.9.13.1.5.1.2.{psu_idx}"
    state_oid = f"1.3.6.1.4.1.9.9.13.1.5.1.4.{psu_idx}"
    return (
        _common_varbinds(device, CISCO_ENV_PSU_STATUS_CHANGE, sequence)
        + _ber_varbind(descr_oid, _ber_octet_string(f"PowerSupply{psu_idx - 1}"))
        + _ber_varbind(state_oid, _ber_integer(4))  # notFunctioning
    )


def _build_config_change(device: MockDevice, sequence: int) -> bytes:
    user_oid = f"1.3.6.1.4.1.9.9.43.1.1.6.1.4.{sequence}"
    cmd_src_oid = f"1.3.6.1.4.1.9.9.43.1.1.6.1.5.{sequence}"
    return (
        _common_varbinds(device, CCM_CLI_RUNNING_CONFIG_CHANGED, sequence)
        + _ber_varbind(user_oid, _ber_octet_string("admin"))
        + _ber_varbind(cmd_src_oid, _ber_integer(1))  # commandLine
    )


def build_gnmi_json_frame(device_id: str, sequence: int, *, source: str = "mock-device") -> dict[str, Any]:
    """Build one parser-compatible line-delimited gNMI/MDT JSON frame."""
    base = 1_700_000_000_000_000_000 + sequence * 1_000_000_000
    return {
        "device_id": device_id,
        "timestamp": base,
        "labels": {"source": source, "simulator": "nms-custom"},
        "updates": [
            {
                "path": "/interfaces/interface[name=GigabitEthernet0/0/0/0]/state/counters/in-octets",
                "value": 100_000 + sequence * 1234,
                "unit": "octets",
                "object_type": "interface",
                "object_id": "GigabitEthernet0/0/0/0",
            },
            {
                "path": "/components/component[name=RP0]/cpu/utilization/state/instant",
                "value": 20 + (sequence % 60),
                "unit": "percent",
                "object_type": "component",
                "object_id": "RP0",
                "quality": "good" if sequence % 7 else "suspect",
            },
        ],
    }


def _ssl_context(url: str) -> ssl.SSLContext | None:
    if not url.startswith("https://"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # local self-signed dev certs only
    return ctx


def _api_request(api_url: str, path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    url = api_url.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=_ssl_context(url), timeout=10) as resp:  # nosec B310 - operator-provided local URL
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def ensure_device(api_url: str, device: MockDevice) -> str:
    """Find or create a mock Device and return its UUID."""
    query = urllib.parse.quote(device.name)
    try:
        existing = _api_request(api_url, f"/devices?q={query}")
        for row in existing or []:
            if row.get("name") == device.name:
                return row["id"]
        created = _api_request(
            api_url,
            "/devices",
            method="POST",
            body={
                "name": device.name,
                "ip_address": device.ip_address,
                "device_type": "router",
                "model": device.platform,
                "vendor": "Cisco",
                "os_type": "IOS XR",
                "status": "online",
                "location": "Mock Lab",
                "site_id": device.site,
                "role": "pe",
                "platform_family": "ios-xr",
                "snmp_enabled": True,
                "telemetry_enabled": True,
                "tags": ["mock", "simulator"],
            },
        )
        return created["id"]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise SystemExit(f"API device bootstrap failed at {api_url}: {exc}") from exc


def emit_syslog(host: str, port: int, device: MockDevice, *, count: int, interval: float) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for seq in range(1, count + 1):
            payload = build_syslog_message(device, seq, alarm=(seq % 5 == 0)).encode("utf-8")
            sock.sendto(payload, (host, port))
            print(f"syslog sent seq={seq} bytes={len(payload)}")
            time.sleep(interval)
    finally:
        sock.close()


def emit_snmp_traps(
    host: str,
    port: int,
    device: MockDevice,
    *,
    count: int,
    interval: float,
    community: str = "public",
    trap_type: str = "link-down",
) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        for seq in range(1, count + 1):
            packet = build_snmp_v2c_trap_packet(device, seq, community=community, trap_type=trap_type)
            sock.sendto(packet, (host, port))
            print(f"trap sent seq={seq} type={trap_type} bytes={len(packet)}")
            time.sleep(interval)
    finally:
        sock.close()


def emit_telemetry(host: str, port: int, device_id: str, *, count: int, interval: float) -> None:
    with socket.create_connection((host, port), timeout=10) as sock:
        file = sock.makefile("rwb")
        for seq in range(1, count + 1):
            frame = build_gnmi_json_frame(device_id, seq)
            payload = (json.dumps(frame, separators=(",", ":")) + "\n").encode("utf-8")
            file.write(payload)
            file.flush()
            response = file.readline().decode("utf-8", errors="replace").strip()
            print(f"telemetry sent seq={seq} response={response}")
            time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="NMS_Custom mock device simulator")
    parser.add_argument("--api-url", default="https://localhost:8000/api")
    parser.add_argument("--name", default="mock-iosxr-1")
    parser.add_argument("--ip", default="10.255.0.11")
    parser.add_argument("--platform", default="IOS XRv 9000")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ensure = sub.add_parser("ensure-device", help="create/find mock device via API")

    syslog_p = sub.add_parser("syslog", help="emit UDP syslog events")
    syslog_p.add_argument("--host", default="127.0.0.1")
    syslog_p.add_argument("--port", type=int, default=5514)
    syslog_p.add_argument("--count", type=int, default=10)
    syslog_p.add_argument("--interval", type=float, default=1.0)

    trap_p = sub.add_parser("trap", help="emit raw SNMPv2c traps (link-down, link-up, bgp-down, ospf-down, fan-fail, psu-fail, config-change)")
    trap_p.add_argument("--host", default="127.0.0.1")
    trap_p.add_argument("--port", type=int, default=1162)
    trap_p.add_argument("--community", default="public")
    trap_p.add_argument("--count", type=int, default=10)
    trap_p.add_argument("--interval", type=float, default=1.0)
    trap_p.add_argument(
        "--trap-type",
        default="link-down",
        choices=list(VALID_TRAP_TYPES),
        help="Type of SNMP trap to emit",
    )

    telemetry_p = sub.add_parser("telemetry", help="emit line-delimited gNMI JSON telemetry")
    telemetry_p.add_argument("--host", default="127.0.0.1")
    telemetry_p.add_argument("--port", type=int, default=57400)
    telemetry_p.add_argument("--device-id", default="")
    telemetry_p.add_argument("--count", type=int, default=10)
    telemetry_p.add_argument("--interval", type=float, default=1.0)

    run_p = sub.add_parser("run", help="ensure device, then emit syslog and telemetry")
    run_p.add_argument("--syslog-host", default="127.0.0.1")
    run_p.add_argument("--syslog-port", type=int, default=5514)
    run_p.add_argument("--trap-host", default="127.0.0.1")
    run_p.add_argument("--trap-port", type=int, default=1162)
    run_p.add_argument("--telemetry-host", default="127.0.0.1")
    run_p.add_argument("--telemetry-port", type=int, default=57400)
    run_p.add_argument("--count", type=int, default=10)
    run_p.add_argument("--interval", type=float, default=1.0)

    args = parser.parse_args()
    device = MockDevice(name=args.name, ip_address=args.ip, platform=args.platform)

    if args.cmd == "ensure-device":
        print(ensure_device(args.api_url, device))
    elif args.cmd == "syslog":
        emit_syslog(args.host, args.port, device, count=args.count, interval=args.interval)
    elif args.cmd == "trap":
        ensure_device(args.api_url, device)
        emit_snmp_traps(
            args.host,
            args.port,
            device,
            count=args.count,
            interval=args.interval,
            community=args.community,
            trap_type=args.trap_type,
        )
    elif args.cmd == "telemetry":
        device_id = args.device_id or ensure_device(args.api_url, device)
        emit_telemetry(args.host, args.port, device_id, count=args.count, interval=args.interval)
    elif args.cmd == "run":
        device_id = ensure_device(args.api_url, device)
        emit_syslog(args.syslog_host, args.syslog_port, device, count=args.count, interval=args.interval)
        emit_snmp_traps(args.trap_host, args.trap_port, device, count=args.count, interval=args.interval)
        emit_telemetry(args.telemetry_host, args.telemetry_port, device_id, count=args.count, interval=args.interval)
    else:  # pragma: no cover
        parser.error("unknown command")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
