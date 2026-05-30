#!/usr/bin/env python3
"""Build remaining NCS540L_CE chassis-view profiles from real EPNM assets.

Covers five new NCS540 / NCS540X variants that have clean EPNM SVG + slot data
but no dedicated normalized.json yet.  Component data is reused from the existing
ncs540 profile (same approach as build_ncs540_12z16g_chassis_profile.py).

Profiles generated:
  ncs540-28z4c     N540-28Z4C-SYS-D (and -A detection alias)
  ncs540-12z20g    N540-12Z20G-SYS-D (and -A detection alias)
  ncs540-fh-agg    N540-FH-AGG-SYS
  ncs540-fh-csr    N540-FH-CSR-SYS
  ncs540x-4z14g2q  N540X-4Z14G2Q-D  (and -A detection alias)

Detection aliases that reuse existing profiles (no new normalized.json needed):
  N540X-16Z4G8Q2C-A  → ncs540-16z4   (same layout, AC power variant)
  N540X-12Z16G-SYS-A → ncs540-12z16g (same layout, AC power variant)

Run: python3 scripts/build_ncs540_remaining_variants.py
"""

from __future__ import annotations

import copy
import json
import shutil
import datetime as _dt
from datetime import timezone as _tz
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

# Source component data — reuse existing ncs540 profile (N540X-12Z16G-SYS-D data)
COMPONENT_SOURCE = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs540" / "normalized.json"

EPNM_ROOT = (
    REPO_ROOT
    / "docs"
    / "chassisview_figures"
    / "chassisview"
    / "com.cisco.prime.deviceprofile"
    / "NCS540L_CE"
)
PLUGGABLES = EPNM_ROOT / "pluggables" / "images" / "horizontal"


# ---------------------------------------------------------------------------
# Profile definitions — each entry drives one normalized.json + SVG copy
# ---------------------------------------------------------------------------

PROFILES: list[dict[str, Any]] = [
    # ------------------------------------------------------------------
    # N540-28Z4C-SYS-D  (NCS 540 28x10G + 4x100G, DC power)
    # SVG viewBox: 0 0 1660 165
    # EPNM slots: RP at x=405/y=14, PSU at x=70/y=20
    # SVG rects: PSU box x=74 y=51 w=199 h=62 (two PSUs stacked/adjacent)
    # ------------------------------------------------------------------
    {
        "key": "ncs540-28z4c",
        "profile_id": "Cisco_NCS_540-28Z4C-SYS-D",
        "device_id": "example-ncs540-28z4c",
        "platform": "Cisco NCS 540 (N540-28Z4C-SYS-D)",
        "svg_src": EPNM_ROOT / "Cisco_NCS_540-28Z4C-SYS-D_Router" / "images" / "N540-28Z4C-SYS-D_front_core.svg",
        "svg_name": "NCS540-28Z4C-Front.svg",
        "canvas_w": 1660,
        "canvas_h": 165,
        "epnm_svg": "NCS540L_CE/Cisco_NCS_540-28Z4C-SYS-D_Router/images/N540-28Z4C-SYS-D_front_core.svg",
        # RP covers the main board area from x=405 to near right edge
        # PSU: two side-by-side PSUs in x=74 y=51 w=199 area; split each 100px wide
        "hotspots": [
            {
                "slot": "rp",
                "id": "hotspot-rp-1",
                "bounds": (405, 5, 1240, 155),   # RP: from EPNM x=405, spans most of remaining width
                "physindex_key": "rp",
                "asset": "N540-28Z4C-SYS-D-RSP",
            },
            {
                "slot": "pm0",
                "id": "hotspot-power-pm0",
                "bounds": (74, 51, 99, 62),        # left PSU slot
                "physindex_key": "pm0",
                "asset": "N540-28Z4C-SYS-D-PSU",
            },
            {
                "slot": "pm1",
                "id": "hotspot-power-pm1",
                "bounds": (174, 51, 99, 62),       # right PSU slot
                "physindex_key": "pm1",
                "asset": "N540-28Z4C-SYS-D-PSU",
            },
        ],
        "module_svgs": {},   # no matching pluggable SVGs available
        "note": "Component data reused from ncs540 profile; hotspot bounds from EPNM slot analysis.",
    },

    # ------------------------------------------------------------------
    # N540-12Z20G-SYS-D  (NCS 540 12x100G + 20x1G, DC power, 2RU-like)
    # SVG viewBox: 0 0 1680 165
    # EPNM slots: RP x=395/y=12, PSU_0 x=170/y=55, PSU_1 x=76/y=55, Fan x=46/y=5
    # ------------------------------------------------------------------
    {
        "key": "ncs540-12z20g",
        "profile_id": "Cisco_NCS_540-12Z20G-SYS-D",
        "device_id": "example-ncs540-12z20g",
        "platform": "Cisco NCS 540 (N540-12Z20G-SYS-D)",
        "svg_src": EPNM_ROOT / "Cisco_NCS_540-12Z20G-SYS-D_Router" / "images" / "N540-12Z20G-SYS-D_front_core.svg",
        "svg_name": "NCS540-12Z20G-Front.svg",
        "canvas_w": 1680,
        "canvas_h": 165,
        "epnm_svg": "NCS540L_CE/Cisco_NCS_540-12Z20G-SYS-D_Router/images/N540-12Z20G-SYS-D_front_core.svg",
        "hotspots": [
            {
                "slot": "rp",
                "id": "hotspot-rp-1",
                "bounds": (395, 5, 1265, 155),   # RP: from x=395, wide enough to cover board
                "physindex_key": "rp",
                "asset": "N540-12Z20G-SYS-D-RSP",
            },
            {
                "slot": "pm0",
                "id": "hotspot-power-pm0",
                "bounds": (76, 55, 85, 75),       # PSU_1 (left)
                "physindex_key": "pm0",
                "asset": "N540-12Z20G-SYS-D-PSU",
            },
            {
                "slot": "pm1",
                "id": "hotspot-power-pm1",
                "bounds": (170, 55, 85, 75),      # PSU_0 (right)
                "physindex_key": "pm1",
                "asset": "N540-12Z20G-SYS-D-PSU",
            },
            {
                "slot": "fan",
                "id": "hotspot-fan-ft0",
                "bounds": (5, 5, 65, 155),        # Fan tray (left side, x=46 anchor)
                "physindex_key": "fan",
                "asset": "N540-12Z20G-SYS-D-FAN",
            },
        ],
        "module_svgs": {
            "N540-12Z20G-SYS-D-RSP": PLUGGABLES / "N540-12Z20G-SYS-D_front_RSP.svg",
            "N540-12Z20G-SYS-D-PSU": PLUGGABLES / "N540-12Z20G-SYS-D_front_dcpower.svg",
        },
        "note": "Component data reused from ncs540 profile; hotspot bounds from EPNM slot analysis.",
    },

    # ------------------------------------------------------------------
    # N540-FH-AGG-SYS  (NCS 540 FH Aggregation, 2RU chassis)
    # SVG viewBox: 0 0 1680 165
    # EPNM slots: RP x=292/y=21, PSU_0 x=56/y=4, PSU_1 x=1427/y=4
    #             Fan x=319/y=8, x=486/y=8, x=655/y=8 (3 fans)
    # ------------------------------------------------------------------
    {
        "key": "ncs540-fh-agg",
        "profile_id": "Cisco_NCS_540-FH-AGG-SYS",
        "device_id": "example-ncs540-fh-agg",
        "platform": "Cisco NCS 540 FH Aggregation (N540-FH-AGG-SYS)",
        "svg_src": EPNM_ROOT / "Cisco_NCS_540-FH-AGG-SYS_Router" / "images" / "N540-FH-AGG-SYS_Front_Core.svg",
        "svg_name": "NCS540-FH-AGG-Front.svg",
        "canvas_w": 1680,
        "canvas_h": 165,
        "epnm_svg": "NCS540L_CE/Cisco_NCS_540-FH-AGG-SYS_Router/images/N540-FH-AGG-SYS_Front_Core.svg",
        "hotspots": [
            {
                "slot": "pm0",
                "id": "hotspot-power-pm0",
                "bounds": (10, 5, 130, 155),      # Left PSU (x=56 anchor)
                "physindex_key": "pm0",
                "asset": None,
            },
            {
                "slot": "pm1",
                "id": "hotspot-power-pm1",
                "bounds": (1395, 5, 120, 155),    # Right PSU (x=1427 anchor)
                "physindex_key": "pm1",
                "asset": None,
            },
            {
                "slot": "rp",
                "id": "hotspot-rp-1",
                "bounds": (170, 5, 1220, 155),    # RP: from after left PSU to before fans
                "physindex_key": "rp",
                "asset": None,
            },
            {
                "slot": "fan0",
                "id": "hotspot-fan-ft0",
                "bounds": (1530, 5, 50, 155),     # Fan 0
                "physindex_key": "fan",
                "asset": None,
            },
        ],
        "module_svgs": {},
        "note": "Component data reused from ncs540 profile; hotspot bounds from EPNM slot analysis.",
    },

    # ------------------------------------------------------------------
    # N540-FH-CSR-SYS  (NCS 540 FH CSR, 2RU chassis)
    # SVG viewBox: 0 0 1680 165
    # EPNM slots: RP x=523/y=9, PSU_0 x=26/y=4, PSU_1 x=252/y=6, Fan x=42/y=10
    # ------------------------------------------------------------------
    {
        "key": "ncs540-fh-csr",
        "profile_id": "Cisco_NCS_540-FH-CSR-SYS",
        "device_id": "example-ncs540-fh-csr",
        "platform": "Cisco NCS 540 FH CSR (N540-FH-CSR-SYS)",
        "svg_src": EPNM_ROOT / "Cisco_NCS_540-FH-CSR-SYS_Router" / "images" / "N540-FH-CSR-SYS_Front_Core.svg",
        "svg_name": "NCS540-FH-CSR-Front.svg",
        "canvas_w": 1680,
        "canvas_h": 165,
        "epnm_svg": "NCS540L_CE/Cisco_NCS_540-FH-CSR-SYS_Router/images/N540-FH-CSR-SYS_Front_Core.svg",
        "hotspots": [
            {
                "slot": "pm0",
                "id": "hotspot-power-pm0",
                "bounds": (10, 5, 120, 155),      # Left PSU (x=26 anchor)
                "physindex_key": "pm0",
                "asset": None,
            },
            {
                "slot": "pm1",
                "id": "hotspot-power-pm1",
                "bounds": (140, 5, 120, 155),     # Second PSU (x=252 anchor area)
                "physindex_key": "pm1",
                "asset": None,
            },
            {
                "slot": "fan",
                "id": "hotspot-fan-ft0",
                "bounds": (270, 5, 60, 155),      # Fan tray (x=42/area)
                "physindex_key": "fan",
                "asset": None,
            },
            {
                "slot": "rp",
                "id": "hotspot-rp-1",
                "bounds": (340, 5, 1320, 155),    # RP: from x=523 anchor, covers main board
                "physindex_key": "rp",
                "asset": None,
            },
        ],
        "module_svgs": {},
        "note": "Component data reused from ncs540 profile; hotspot bounds from EPNM slot analysis.",
    },

    # ------------------------------------------------------------------
    # N540X-4Z14G2Q-D  (NCS 540X 4x100G + 14x25G + 2x100G, DC power)
    # SVG viewBox: 0 0 1680 166
    # EPNM slots: RP x=684/y=36, PSU_0 x=200/y=36, PSU_1 x=380/y=46
    # SVG rects: RP at x=682 y=37 w=122 h=98, PSU area x=207 y=62 w=206 h=65
    # ------------------------------------------------------------------
    {
        "key": "ncs540x-4z14g2q",
        "profile_id": "Cisco_NCS_540X-4Z14G2Q-D",
        "device_id": "example-ncs540x-4z14g2q",
        "platform": "Cisco NCS 540X (N540X-4Z14G2Q-D)",
        "svg_src": EPNM_ROOT / "Cisco_NCS_540X-4Z14G2Q-D_Router" / "images" / "N540X-4Z14G2Q-D_font_core.svg",
        "svg_name": "NCS540X-4Z14G2Q-Front.svg",
        "canvas_w": 1680,
        "canvas_h": 166,
        "epnm_svg": "NCS540L_CE/Cisco_NCS_540X-4Z14G2Q-D_Router/images/N540X-4Z14G2Q-D_font_core.svg",
        "hotspots": [
            {
                "slot": "pm0",
                "id": "hotspot-power-pm0",
                "bounds": (207, 4, 103, 158),     # Left PSU (x=200 anchor)
                "physindex_key": "pm0",
                "asset": None,
            },
            {
                "slot": "pm1",
                "id": "hotspot-power-pm1",
                "bounds": (310, 4, 103, 158),     # Right PSU (x=380 anchor area)
                "physindex_key": "pm1",
                "asset": None,
            },
            {
                "slot": "rp",
                "id": "hotspot-rp-1",
                "bounds": (682, 4, 984, 158),     # RP/board (x=684 anchor, extends right)
                "physindex_key": "rp",
                "asset": None,
            },
        ],
        "module_svgs": {},
        "note": "Component data reused from ncs540 profile; hotspot bounds from EPNM slot analysis.",
    },
]


# ---------------------------------------------------------------------------
# Helper: build a hotspot entry from component data + bounds
# ---------------------------------------------------------------------------

def make_hotspot(
    comp: dict[str, Any],
    hid: str,
    bounds: tuple[int, int, int, int],
    asset_typeid: str | None,
    profile_key: str,
) -> dict[str, Any]:
    x, y, w, h = bounds
    out: dict[str, Any] = {
        "id": hid,
        "inventoryId": comp["id"],
        "physicalIndex": comp["physicalIndex"],
        "label": comp.get("name") or comp.get("description") or comp["id"],
        "slotKey": comp.get("slotKey") or comp.get("name"),
        "bounds": {"x": x, "y": y, "w": w, "h": h},
        "empty": comp.get("modelName") in (None, "", "N/A"),
        "metadata": {
            "modelName": comp.get("modelName"),
            "modelTypeId": comp.get("modelName"),
            "sourceName": comp.get("name"),
            "sourceTypeId": comp.get("modelName"),
        },
    }
    if asset_typeid:
        rel = f"/chassis-assets/{profile_key}/modules/{asset_typeid}.svg"
        out["asset"] = {"typeId": asset_typeid, "image": rel, "sourceImage": rel}
    return out


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build() -> None:
    # Load component data from existing ncs540 profile
    src = json.loads(COMPONENT_SOURCE.read_text(encoding="utf-8"))
    components: dict[str, Any] = src["componentsById"]
    by_idx: dict[int, dict[str, Any]] = {c["physicalIndex"]: c for c in components.values()}

    # Key physical indices from the ncs540 source profile (N540X-12Z16G-SYS-D walk)
    rp_comp   = by_idx[1]     # 0/RP0/CPU0
    pm0_comp  = by_idx[8982]  # 0/PM0
    pm1_comp  = by_idx[13078] # 0/PM1
    # Fan — pick one if available, else reuse RP as placeholder
    fan_comp  = next(
        (c for c in components.values() if "FT" in (c.get("name") or "") or "Fan" in (c.get("description") or "")),
        rp_comp,
    )

    slot_to_comp = {
        "rp":   rp_comp,
        "pm0":  pm0_comp,
        "pm1":  pm1_comp,
        "fan":  fan_comp,
        "fan0": fan_comp,
    }

    for pdef in PROFILES:
        key = pdef["key"]
        backend_out  = REPO_ROOT / "backend"  / "app" / "data" / "chassis" / key
        frontend_out = REPO_ROOT / "frontend" / "public" / "chassis-assets" / key

        for out_dir in (backend_out, frontend_out):
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "modules").mkdir(exist_ok=True)

        # Copy main SVG
        if not pdef["svg_src"].exists():
            print(f"  [SKIP] SVG not found: {pdef['svg_src']}")
            continue
        shutil.copyfile(pdef["svg_src"], backend_out  / pdef["svg_name"])
        shutil.copyfile(pdef["svg_src"], frontend_out / pdef["svg_name"])

        # Copy module SVGs
        for typeid, src_path in pdef.get("module_svgs", {}).items():
            if src_path.exists():
                shutil.copyfile(src_path, backend_out  / "modules" / f"{typeid}.svg")
                shutil.copyfile(src_path, frontend_out / "modules" / f"{typeid}.svg")
            else:
                print(f"  [WARN] Module SVG not found: {src_path}")

        # Build hotspot list
        hotspots = []
        for hs in pdef["hotspots"]:
            comp = slot_to_comp[hs["slot"]]
            hotspots.append(make_hotspot(
                comp=comp,
                hid=hs["id"],
                bounds=hs["bounds"],
                asset_typeid=hs.get("asset"),
                profile_key=key,
            ))

        profile = {
            "schemaVersion": "nms.chassisView.v1",
            "profileId": pdef["profile_id"],
            "deviceId": pdef["device_id"],
            "platform": pdef["platform"],
            "generatedAt": _dt.datetime.now(_tz.utc).isoformat(),
            "source": {
                "profile": "backend/app/data/chassis/ncs540/normalized.json",
                "type": "entity-mib-derived-static-profile",
                "epnmSvg": pdef["epnm_svg"],
                "note": pdef.get("note", ""),
            },
            "componentsById": components,
            "physicalIndexToComponentId": src.get("physicalIndexToComponentId", {}),
            "tree": src.get("tree", []),
            "views": [
                {
                    "id": "front",
                    "label": "Front View",
                    "image": f"/chassis-assets/{key}/{pdef['svg_name']}",
                    "width": pdef["canvas_w"],
                    "height": pdef["canvas_h"],
                    "sourceWidth":  pdef["canvas_w"],
                    "sourceHeight": pdef["canvas_h"],
                    "hotspots": hotspots,
                }
            ],
        }

        for out_dir in (backend_out, frontend_out):
            (out_dir / "normalized.json").write_text(
                json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print(f"[OK]  {key}  →  {len(hotspots)} hotspots  |  {pdef['svg_name']}")

    print("\nDone. Next step: add detection rules to backend/app/api/devices.py")


if __name__ == "__main__":
    build()
