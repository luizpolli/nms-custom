# Cisco ASR 5000 (ASR5k) chassis-view status

## Status: not supported

The NMS does not currently ship a chassis-view profile for the Cisco
ASR 5000 family.

## Why

- **Platform mismatch.** ASR 5000 is the StarOS mobile packet core
  platform (originally Starent Networks). It uses an ATCA-style
  modular chassis with line cards, switch processor cards, and a
  packet processing fabric — architecturally quite different from the
  IOS-XR / IOS-XE EPNM device profile packs we consume for NCS5xx,
  NCS540, NCS560, ASR9xxx, and ASR9xx.
- **No EPNM assets available.** The Cisco Prime / EPNM chassis-view
  asset bundles we have do not include an ASR 5000 device profile,
  pluggable SVG set, or front/rear images.
- **No SNMP fixtures.** `docs/snmpwalks/` and `docs/snmpwalks/normalized/`
  contain no ASR 5000 ENTITY-MIB walks; the SNMP MIB modules the
  StarOS platform exposes also diverge from IOS-XR ENTITY-MIB layout
  in non-trivial ways.
- **No production demand recorded.** No backend chassis profile entry
  in `backend/app/api/devices.py` `_CHASSIS_PROFILE_FILES`, no
  pattern in the `compact_terms`-based `_pick_chassis_profile`
  matcher, no tests, no UI references.

## What we did

- Removed the orphan `'asr5k'` literal from `DevicePlatform` in
  `frontend/src/lib/types.ts`. The `| string` fallback in the union
  means any future device with `platform="asr5k"` still type-checks;
  the platform just won't render a chassis view until a profile is
  added.
- Added this note so anyone running into the gap finds the context
  instead of guessing.

## What it would take to add it later

If we ever need to support ASR 5000:

1. Obtain a real chassis SVG (likely from Cisco PEM/Prime equivalent
   for StarOS, or hand-trace from a product datasheet).
2. Capture an ENTITY-MIB-equivalent walk from a representative ASR
   5500 / VPC-DI deployment, or build a synthetic profile from the
   StarOS `show card` / `show hardware` output.
3. Add a `Cisco_ASR_5500_Chassis` profile JSON under
   `backend/app/data/chassis/asr5500/` with the canonical hotspot
   shape used by the rest of the codebase.
4. Wire it into `_CHASSIS_PROFILE_FILES` and `_pick_chassis_profile`
   in `backend/app/api/devices.py`.
5. Re-add `'asr5k'` (or the more specific PID) to the `DevicePlatform`
   union when we want compile-time guidance for it.

Until then this platform is intentionally absent.
