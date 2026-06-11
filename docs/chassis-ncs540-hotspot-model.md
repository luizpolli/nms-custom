# NCS540 chassis-view hotspot model

## TL;DR

The `N540X-12Z16G-SYS-D` chassis profile in our `normalized.json`
exposes 33 hotspots (1 RP + 28 bays + 1 fan + 2 PSU + 1 chassis), while
the upstream EPNM profile JSON declares only 2 top-level slots
(`Rack_0-RouteProcessor_Slot_0`, `Rack_0-PSU_Slot_0`). This is **not a
bug** — the two systems model the chassis at different granularities and
we intentionally pick the higher-resolution one.

## Why the numbers differ

| Source | Granularity | Count |
|---|---|---|
| EPNM `Cisco_NCS_540X-12Z16G-SYS-D_Router.json` | Top-level slots only (RP card, PSU bay) | 2 |
| Our `normalized.json` (from ENTITY-MIB walk) | Every selectable inventory object | 33 |

EPNM uses the chassis SVG to render the RP card as a single image, and
relies on the RP card's internal SVG (`N540X-12Z16G-SYS-D_RSP.svg`) to
draw the 28 ports as part of the card artwork. EPNM only generates
hotspots for the top-level slots because that is the granularity at
which a physical FRU can be inserted / removed.

For the NMS we want per-port selection (alarms, live link state,
optical telemetry, configuration), so we flatten the SNMP inventory
into one hotspot per selectable component:

- 1 × Route Processor (`0/RP0/CPU0`)
- 4 × fixed 1G copper RJ45 (front-panel ports 0/0/0 – 0/0/3)
- 12 × 1G SFP bays (0/0/4 – 0/0/15)
- 12 × 10G SFP+ bays (0/0/16 – 0/0/27)
- 1 × fan tray (`0/FT0`)
- 2 × PSU (`0/PM0`, `0/PM1`)
- 1 × chassis backplate (`Rack 0`)

That's 33 hotspots — matches what the chassis-view renders.

## Visual overlap with the RP card

The RP hotspot's bounds (x=521, y=4, w=1088, h=154) cover the full RP
card image, which includes the area where the 28 port bays are drawn.
The bay hotspots (x=800..1583) sit inside the RP rectangle.

This is harmless because:

1. The RP card is the **`SlotAsset`** image (purely visual), drawn on
   top of the chassis backdrop.
2. The clickable buttons are emitted in array order. Bays come after
   the RP in the array, so in DOM order they're rendered after and sit
   above the RP button.
3. Clicking inside a bay's bounds hits the bay button first; clicking
   inside the RP card but outside any bay (LEDs, labels, mgmt area
   on the left) correctly hits the RP button.

## Cu vs optical bays

The "12x10G + 4x1G Cu + 12x1G" product naming refers to:

- **4 fixed 1G copper RJ45**: inventory description = `Fixed Port Container`.
- **12 + 12 = 24 pluggable optics**: inventory description = `Pluggable Optical Module Container`.

The `slotKey` from the SNMP walk labels every bay as `SFP bay N` even
for the RJ45 ports (the slotKey reflects the OID context, not the
physical media). The asset patcher distinguishes them by inventory
description and routes the 4 copper bays to a locally synthesized
`RJ45.svg`, while pluggables use the EPNM generic `SFP.svg` (with the
real transceiver PID preserved in `asset.typeId`).

## See also

- `scripts/archive/chassis-migration/patch_ncs540_asr920_assets.py` — asset population logic.
- `frontend/public/chassis-assets/ncs540/modules/RJ45.svg` — local RJ45 glyph.
- EPNM source: `docs/chassisview_figures/.../NCS540L_CE/Cisco_NCS_540X-12Z16G-SYS-D_Router/`.
