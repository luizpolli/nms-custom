# Mock Device Simulators

Use these helpers when you want traffic that looks like Cisco devices without needing hardware.

## What is covered

- UDP syslog messages to `syslog-receiver` (`localhost:5514` by default).
- Raw SNMPv2c linkDown/linkUp traps to `trap-receiver` (`localhost:1162` by default).
- Line-delimited gNMI/MDT-style JSON telemetry frames to `telemetry-receiver` (`localhost:57400` by default).
- API bootstrap for a mock Cisco device so telemetry samples reference a real `devices.id`.

This is not a replacement for real IOS XR/NX-OS/IOS XE protocol testing. It is a local integration harness for receivers, event bus publication, workers, KPI normalization, alarms, and UI flows.

## Start local stack

```bash
docker compose up --build -d
```

The Compose default for `telemetry-receiver` is `TELEMETRY_TRANSPORT=gnmi-json` so the simulator can connect immediately.

## Create/find a mock device

```bash
make sim-device
```

Equivalent:

```bash
python tools/simulators/mock_device.py ensure-device
```

Defaults:

- API: `https://localhost:8000/api`
- name: `mock-iosxr-1`
- IP: `10.255.0.11`

## Emit syslog

```bash
make sim-syslog COUNT=20
```

The simulator sends Cisco-ish BSD syslog messages. Every fifth message is a `%LINK-3-UPDOWN` alarm-like event.

## Emit SNMP traps

```bash
make sim-trap COUNT=20
```

The simulator builds minimal SNMPv2c Trap-PDUs directly, so local trap generation does **not** depend on `pysnmp`. The default trap type is `link-down`. Use `--trap-type` to emit other Cisco trap variants:

```bash
python tools/simulators/mock_device.py trap \
  --host 127.0.0.1 --port 1162 --count 5 \
  --trap-type bgp-down
```

Supported `--trap-type` values:

| Value | Trap OID | Notes |
|---|---|---|
| `link-down` | `1.3.6.1.6.3.1.1.5.3` | Standard IF-MIB linkDown |
| `link-up` | `1.3.6.1.6.3.1.1.5.4` | Standard IF-MIB linkUp (clear) |
| `bgp-down` | `1.3.6.1.4.1.9.9.187.0.0.1` | Cisco BGP MIB v2 cbgpPeer2StateChanged |
| `ospf-down` | `1.3.6.1.2.1.14.16.2.2` | OSPF-MIB ospfNbrStateChange |
| `fan-fail` | `1.3.6.1.4.1.9.9.13.3.0.1` | Cisco ENV MON fan status change |
| `psu-fail` | `1.3.6.1.4.1.9.9.13.3.0.3` | Cisco ENV MON PSU redundant supply |
| `config-change` | `1.3.6.1.4.1.9.9.43.2.0.2` | Cisco Config Man MIB ccmCLIRunningConfigChanged |

The payload always includes `sysName.0=<device-name>`, allowing alarm correlation to attach traps to the mock device even when Docker rewrites the UDP source IP.

## Emit telemetry

```bash
make sim-telemetry COUNT=20
```

The simulator creates/finds the mock device, then sends parser-compatible gNMI JSON frames with interface counters and CPU utilization.

## Run all simulators

```bash
make sim-run COUNT=20
```

This sends syslog first, then SNMP traps, then telemetry. Watch services with:

```bash
docker compose logs -f syslog-receiver trap-receiver telemetry-receiver worker-alarm worker-telemetry app
```

## Custom targets

```bash
python tools/simulators/mock_device.py run \
  --api-url https://localhost:8000/api \
  --name mock-iosxr-pe1 \
  --ip 10.255.0.21 \
  --syslog-host 127.0.0.1 \
  --syslog-port 5514 \
  --trap-host 127.0.0.1 \
  --trap-port 1162 \
  --telemetry-host 127.0.0.1 \
  --telemetry-port 57400 \
  --count 50 \
  --interval 0.2
```

## Current limits

- Native gNMI protobuf/gRPC interop still requires lab devices or captures.
- Full async integration test for trap_receiver (live UDP socket) is deferred; the classifier is fully tested at the parsing level.
