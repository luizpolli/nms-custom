# Native gNMI proto scaffolding

This directory is a placeholder for future protobuf/gRPC code generation
against the upstream OpenConfig gNMI definitions:

- https://github.com/openconfig/gnmi/tree/master/proto/gnmi

## Pinning policy

We do NOT vendor the upstream `.proto` files until we have a lab device or a
captured `Subscribe` stream to validate against. The current
`backend/app/services/telemetry/native_gnmi.py` defines a `NativeGnmiAdapter`
protocol and a `StubNativeGnmiAdapter` so the rest of the telemetry pipeline
can be exercised end-to-end without gRPC.

## Codegen target (future)

When the lab is ready:

1. Drop `gnmi.proto` and its transitive deps under `proto/openconfig/`.
2. Use `grpc_tools.protoc` to generate Python stubs into
   `backend/app/services/telemetry/_gnmi_pb/`.
3. Implement a real adapter in `backend/app/services/telemetry/native_gnmi.py`
   that satisfies the `NativeGnmiAdapter` protocol and is selected when
   `TELEMETRY_TRANSPORT=gnmi-native`.
4. Enforce `validate_native_gnmi_tls(config)` at startup; never accept
   `require_mutual_tls=False` in production.

## Why not vendor now

- Without a real Subscribe trace we cannot prove field-by-field equivalence
  against vendor implementations.
- Pinning a snapshot now risks divergence from the upstream OpenConfig repo by
  the time we actually connect to hardware.
