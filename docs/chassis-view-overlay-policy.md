# Chassis View — Overlay Render Policy

> If you read only one paragraph: when a chassis shows duplicated
> ports/PSUs/fans on top of its base SVG, **do not delete the `asset`
> entries from `normalized.json`**.  Add a one-line entry to
> `frontend/src/pages/inventory/chassis/overlayPolicy.ts` instead.

## Background

Each chassis view is composed of two layers:

1. **Base SVG** (`/chassis-assets/<profile>/<Front>.svg`) imported from EPNM
   device profile packs.  Some packs are *full artwork* (every SFP, PSU and
   fan tray is drawn at the pixel level).  Others are *frame-only* (just the
   chassis outline and slot boundaries).
2. **Hotspot overlays** (`view.hotspots[].asset`) — per-PID SVGs rendered on
   top of the base by `<SlotAsset>` inside `ChassisView.tsx`.

When the base SVG is full artwork and we also render an overlay, the user
sees **two copies of the same port** slightly offset.  That is the
"superimposed ports" bug.

## Why the overlay isn't just deleted from the JSON

Hotspot `asset` entries carry metadata that is used beyond rendering:

| Consumer                | Field used                |
|-------------------------|---------------------------|
| `PortDetailPanel`       | `asset.image`, `asset.typeId` |
| Alarm correlation       | `slotKey` + component `typeId` |
| Inspector / search      | `asset.typeId` (real PID) |

Deleting `asset` to fix a visual bug breaks all of the above.  That mistake
was made in commit `fc9dad3` and reverted in `ec5c9a2` — see
`memory/2026-06-04.md`.

## How to add a new entry

1. Open the chassis in the UI at a normal viewport (~1280px).
2. Identify the duplicated hotspot type by hovering — `hotspot.id` follows
   the shape `hotspot-<type>-<n>` (`hotspot-sfp-3`, `hotspot-bay-801`,
   `hotspot-qsfp28-0`).
3. Edit `frontend/src/pages/inventory/chassis/overlayPolicy.ts` and add:

   ```ts
   export const OVERLAY_POLICY: OverlayPolicy = {
     '<profileId>': {
       '<type>': false,
     },
   };
   ```

4. Reload the page (Vite HMR picks the change up).
5. Commit with a message that mentions the profile and the type, e.g.
   `chassis(asr920): disable sfp/uplink/psu overlays (base svg already paints them)`.

## How to revert an entry

Delete the line, reload, done.  No data migration, no JSON repopulation.

## What NOT to do

- ❌ Do **not** run a bulk script that strips `asset` from
  `normalized.json` across multiple profiles.
- ❌ Do **not** "panic revert" overlays — the bug is presentation, fix it
  in presentation.
- ❌ Do **not** treat the heuristic in `scripts/diagnose_chassis_overlays.py`
  as ground truth.  It is a smell detector for SVG path density, not a
  reliable classifier (EPNM SVGs use very large shared paths that defeat
  bbox containment checks).

## Current entries

See the source file for the live list:
[`frontend/src/pages/inventory/chassis/overlayPolicy.ts`](../frontend/src/pages/inventory/chassis/overlayPolicy.ts).

## Related

- `scripts/diagnose_chassis_overlays.py` — diagnostic script, heuristic only.
- `docs/chassis-view.md` — chassis profile developer reference.
- `frontend/src/pages/inventory/chassis/ChassisView.tsx` — the `<SlotAsset>`
  render branch consults `shouldRenderOverlay()`.
