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

The simulator builds minimal SNMPv2c Trap-PDUs directly, so local trap generation does **not** depend on `pysnmp`. Odd sequences emit `linkDown`; even sequences emit the matching `linkUp` clear for the same simulated interface. The payload includes `sysName.0=mock-iosxr-1`, allowing alarm correlation to attach traps to the mock device even when Docker rewrites the UDP source IP.

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

- SNMP trap generation covers a focused SNMPv2c linkDown/linkUp lab path; broader vendor trap catalogs still need fixtures/captures.
- Native gNMI protobuf/gRPC interop still requires lab devices or captures.
