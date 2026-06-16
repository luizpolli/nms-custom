"""
Calibrate chassis hotspot positions for NCS540L_CE variants:
  - NCS540X-12Z16G-SYS-D  (profile: ncs540-12z16g)
  - NCS540X-16Z4G8Q2C-D   (profile: ncs540-16z4)

Port positions extracted from EPNM RSP pluggable SVGs:
  docs/chassisview_figures/.../NCS540L_CE/pluggables/images/horizontal/
    N540X-12Z16G-SYS-D_RSP.svg   (viewBox 1088x154, offset +518/+4)
    N540X-16Z4G8Q2C-D_RSP.svg   (viewBox 1056x146, offset +240/+12)

12Z16G port layout (28 bays):
  SFP bay  0-3  : GigE Cu RJ45 — merged upper+lower rect bounds
  SFP bay  4-15 : GigabitEthernet SFP — lower rect from RSP SVG
  SFP bay 16-27 : TenGigE SFP+ — top rect from RSP SVG

16Z4G8Q2C port layout (30 bays):
  SFP bay   0-3 : GigE Cu RJ45 (2 columns x 2 rows, leftmost)
  SFP bay  4-11 : TenGigE top row (8 slots, upper half)
  SFP bay 12-19 : TenGigE bottom row (8 slots, lower half)
  SFP bay 20-23 : TwentyFiveGigE top row (4 slots, upper half)
  SFP bay 24-27 : TwentyFiveGigE bottom row (4 slots, lower half)
  QSFP bay 28-29: HundredGigE QSFP28
"""

import json
from pathlib import Path

REPO = Path(__file__).parent.parent
FRONTEND = REPO / "frontend/public/chassis-assets"
BACKEND = REPO / "backend/app/data/chassis"
BASE_MODS = "/chassis-assets/ncs540/modules"


# ---------------------------------------------------------------------------
# Hotspot builder
# ---------------------------------------------------------------------------

def sfp_hotspot(bay: int, x: int, y: int, w: int, h: int,
                slot_type: str, module_img: str) -> dict:
    slot_key = f"{slot_type} bay {bay}"
    return {
        "bounds": {"h": h, "w": w, "x": x, "y": y},
        "empty": True,
        "id": f"hotspot-port-{bay}",
        "inventoryId": None,
        "label": slot_key,
        "metadata": {"sourceName": slot_key, "sourceTypeId": slot_key},
        "physicalIndex": None,
        "slotKey": slot_key,
        "asset": {
            "typeId": slot_type,
            "image": module_img,
            "sourceImage": module_img,
        },
    }


# ---------------------------------------------------------------------------
# NCS540X-12Z16G-SYS-D — profile ncs540-12z16g
# RSP offset: x+518, y+4
# ---------------------------------------------------------------------------
# Positions derived from N540X-12Z16G-SYS-D_RSP.svg rect elements.
# Upper-element rects (y~33-44) mark LED indicator cages above the SFP slot.
# Lower-element rects (y~88-99) mark the actual SFP connector opening.
# Bays 0-3: Cu RJ45 — merged bounds covering both upper LED + lower connector.
# Bays 4-15: SFP GigE — lower rect only.
# Bays 16-27: SFP+ TenGigE — upper rect (only rect, no lower).

_12Z16G_PORTS = [
    # (bay, x, y, w, h, slot_type, module)
    # ---- Cu GigE (bays 0-3): merged upper+lower ----
    (0,  610, 48, 46, 72, "SFP", f"{BASE_MODS}/RJ45.svg"),
    (1,  665, 48, 47, 72, "SFP", f"{BASE_MODS}/RJ45.svg"),
    (2,  745, 38, 52, 92, "SFP", f"{BASE_MODS}/RJ45.svg"),
    (3,  800, 38, 50, 92, "SFP", f"{BASE_MODS}/RJ45.svg"),
    # ---- GigE SFP (bays 4-15): lower-row rects ----
    (4,  880, 95, 48, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    (5,  939, 95, 53, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    (6,  1002, 99, 50, 32, "SFP", f"{BASE_MODS}/SFP.svg"),
    (7,  1061, 99, 42, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (8,  1115, 94, 47, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    (9,  1174, 94, 54, 38, "SFP", f"{BASE_MODS}/SFP.svg"),
    (10, 1249, 95, 55, 37, "SFP", f"{BASE_MODS}/SFP.svg"),
    (11, 1313, 99, 42, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (12, 1366, 95, 48, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    (13, 1425, 95, 53, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    (14, 1488, 99, 42, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (15, 1542, 94, 52, 34, "SFP", f"{BASE_MODS}/SFP.svg"),
    # ---- TenGigE SFP+ (bays 16-27): top-row rects ----
    (16, 881, 36,  47, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (17, 940, 36,  52, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (18, 998, 36,  47, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (19, 1057, 36, 52, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (20, 1115, 36, 52, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (21, 1174, 36, 54, 36, "SFP", f"{BASE_MODS}/SFP.svg"),
    (22, 1250, 36, 48, 28, "SFP", f"{BASE_MODS}/SFP.svg"),
    (23, 1309, 36, 51, 28, "SFP", f"{BASE_MODS}/SFP.svg"),
    (24, 1367, 36, 52, 29, "SFP", f"{BASE_MODS}/SFP.svg"),
    (25, 1426, 36, 51, 28, "SFP", f"{BASE_MODS}/SFP.svg"),
    (26, 1484, 36, 51, 28, "SFP", f"{BASE_MODS}/SFP.svg"),
    (27, 1542, 36, 48, 28, "SFP", f"{BASE_MODS}/SFP.svg"),
]


# ---------------------------------------------------------------------------
# NCS540X-16Z4G8Q2C-D — profile ncs540-16z4
# RSP offset: x+240, y+12
# Slot pitch in TenGigE/25GigE area: 58.5px (55.3 wide + gap)
# Each slot hosts TWO stacked SFP bays; split at y≈70 in RSP coords.
# Cu bays are in the separate leftmost cage (RSP x=3-129).
# ---------------------------------------------------------------------------
# Slot left-edge x values (in RSP coords, +240 for main SVG):
_10G_SLOTS_RSP_X = [139.7, 198.2, 256.6, 315.1, 373.5, 432.0, 490.5, 549.0]
_25G_SLOTS_RSP_X = [628.5, 687.0, 745.5, 804.0]

_X_OFF_16Z4 = 240
_Y_OFF_16Z4 = 12

# Stacked-bay y split (in RSP coords): top half ends at ~69, bottom starts at ~70
_TOP_Y,  _TOP_H  = 24, 46   # RSP y=23.7, height=46
_BOT_Y,  _BOT_H  = 70, 50   # RSP y=70, height=50 (ends at 120)


def _build_16z4_ports() -> list[tuple]:
    ports = []

    # Cu bays 0-3 (2 columns × 2 rows, leftmost cage)
    # RSP col1 x≈14.6-61.8, col2 x≈69.6-116.8; top/bot split at y≈81
    cu_cols = [(14, 47), (70, 47)]  # (left_x, width) in RSP coords
    bay = 0
    for col_x, col_w in cu_cols:
        main_x = col_x + _X_OFF_16Z4
        main_y_top = round(22.7 + _Y_OFF_16Z4)
        main_y_bot = round(81.0 + _Y_OFF_16Z4)
        ports.append((bay, main_x, main_y_top, col_w, 47, "SFP", f"{BASE_MODS}/RJ45.svg"))
        bay += 1
        ports.append((bay, main_x, main_y_bot, col_w, 40, "SFP", f"{BASE_MODS}/RJ45.svg"))
        bay += 1

    # TenGigE bays 4-19: top row (4-11) then bottom row (12-19)
    for slot_x in _10G_SLOTS_RSP_X:
        mx = round(slot_x + _X_OFF_16Z4)
        ports.append((bay, mx, _TOP_Y + _Y_OFF_16Z4, 55, _TOP_H, "SFP", f"{BASE_MODS}/SFP.svg"))
        bay += 1
    for slot_x in _10G_SLOTS_RSP_X:
        mx = round(slot_x + _X_OFF_16Z4)
        ports.append((bay, mx, _BOT_Y + _Y_OFF_16Z4, 55, _BOT_H, "SFP", f"{BASE_MODS}/SFP.svg"))
        bay += 1

    # TwentyFiveGigE bays 20-27: top row (20-23) then bottom row (24-27)
    for slot_x in _25G_SLOTS_RSP_X:
        mx = round(slot_x + _X_OFF_16Z4)
        ports.append((bay, mx, _TOP_Y + _Y_OFF_16Z4, 55, _TOP_H, "SFP", f"{BASE_MODS}/SFP.svg"))
        bay += 1
    for slot_x in _25G_SLOTS_RSP_X:
        mx = round(slot_x + _X_OFF_16Z4)
        ports.append((bay, mx, _BOT_Y + _Y_OFF_16Z4, 55, _BOT_H, "SFP", f"{BASE_MODS}/SFP.svg"))
        bay += 1

    # QSFP bays 28-29 (HundredGigE)
    # Bay 28: RSP(883.8, 24.8, 76.4, 98.4)  → main(1124, 37, 76, 98)
    # Bay 29: RSP(987.0, 12.7, 66.0, 112)   → main(1227, 25, 66, 112)
    ports.append((28, 1124, 37,  76,  98, "QSFP", f"{BASE_MODS}/QSFP.svg"))
    ports.append((29, 1227, 25,  66, 112, "QSFP", f"{BASE_MODS}/QSFP.svg"))

    return ports


_16Z4G8Q2C_PORTS = _build_16z4_ports()


# ---------------------------------------------------------------------------
# Profile registry
# ---------------------------------------------------------------------------

PROFILES = {
    "ncs540-12z16g": {
        "ports": _12Z16G_PORTS,
        "background_ids": {"hotspot-rp-1"},
    },
    "ncs540-16z4": {
        "ports": _16Z4G8Q2C_PORTS,
        "background_ids": {"hotspot-rp-1", "hotspot-fan-4097"},
    },
}


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply(profile: str, cfg: dict, dry_run: bool = False) -> None:
    paths = [
        FRONTEND / profile / "normalized.json",
        BACKEND  / profile / "normalized.json",
    ]

    port_hotspots = [
        sfp_hotspot(bay, x, y, w, h, slot_type, mod)
        for bay, x, y, w, h, slot_type, mod in cfg["ports"]
    ]

    for p in paths:
        if not p.exists():
            print(f"  SKIP (missing): {p}")
            continue

        with open(p) as f:
            data = json.load(f)

        view = data["views"][0]
        existing = view["hotspots"]

        bg_ids = cfg["background_ids"]
        background = [h for h in existing if h["id"] in bg_ids]
        other = [
            h for h in existing
            if h["id"] not in bg_ids and not h["id"].startswith("hotspot-port-")
        ]

        # Port hotspots first → higher click priority; background last
        view["hotspots"] = port_hotspots + other + background

        if dry_run:
            print(f"  [DRY RUN] {len(port_hotspots)} port hotspots → {p}")
            continue

        p.write_text(json.dumps(data, indent=2))
        print(f"  wrote {len(port_hotspots)} port hotspots → {p.relative_to(REPO)}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Calibrate NCS540L_CE chassis hotspots (12Z16G + 16Z4G8Q2C)"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("profiles", nargs="*", default=list(PROFILES))
    args = parser.parse_args()

    for profile in args.profiles:
        if profile not in PROFILES:
            print(f"Unknown profile: {profile}. Valid: {list(PROFILES)}")
            continue
        print(f"\n{profile}:")
        apply(profile, PROFILES[profile], dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
