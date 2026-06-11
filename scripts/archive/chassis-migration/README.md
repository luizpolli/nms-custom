# Archived chassis migration scripts

One-off scripts used during the EPNM SVG asset migration (May–June 2026).
Their output is already committed under `frontend/public/chassis-assets/` and
`backend/app/data/chassis/`; **they are kept for provenance only and are not
expected to run again.** Several hardcode paths to the local EPNM asset
extraction (`.local/chassis-assets/`) that is not part of the repo.

If you need to build or patch a chassis profile today, start from the live
tools in `scripts/`:

- `normalize_snmpwalk_chassis.py` — turn ENTITY-MIB snmpwalk captures into a `normalized.json`
- `normalize_chassis_assets.py` — normalize EPNM SVG/profile assets
- `audit_chassis_assets.py` — audit hotspot/asset coverage across profiles
- `diagnose_chassis_overlays.py` — debug overlay duplication (see `docs/chassis-view-overlay-policy.md`)

## What each archived script did

| Script | Purpose |
|---|---|
| `build_ncs_chassis_profiles.py` | First-generation builder for the NCS55A1/NCS560 profiles |
| `build_ncs55a1_chassis_profile.py` | NCS55A1 profile rebuild from EPNM assets (44 hotspots) |
| `build_asr9010_chassis_profile.py` | ASR9010 profile from EPNM `Cisco_ASR_9010_Router` assets |
| `build_asr920_chassis_profile.py` | ASR920 fixed-port profile; synthesizes sanitized front SVG |
| `build_ncs540_12z16g_chassis_profile.py` | NCS540X-12Z16G variant profile |
| `build_ncs540_16z4_chassis_profile.py` | NCS540X-16Z4G8Q2C variant profile |
| `build_ncs540_remaining_variants.py` | Remaining NCS540 variants (28Z4C, 12Z20G, FH-AGG, FH-CSR, 4Z14G2Q) |
| `patch_ncs55a1_assets.py` | Populate NCS55A1 hotspot `asset` blocks with EPNM module SVGs |
| `patch_ncs560_assets.py` | Same for NCS560 (55 hotspots) |
| `patch_ncs540_assets.py` | Same for NCS540 base profile |
| `patch_ncs540_variants_assets.py` | Same for NCS540 variants |
| `patch_ncs540_asr920_assets.py` | Combined NCS540 + ASR920 asset population pass |
| `patch_static_stub_assets.py` | Populate assets across the remaining stub profiles |

The migration history and format specs live in `docs/CHASSIS_EPNM_MIGRATION.md`.
Overlay render decisions are frozen by
`frontend/src/pages/inventory/chassis/overlaySnapshots.test.ts` — if you
regenerate any `normalized.json`, expect those snapshots to need review.
