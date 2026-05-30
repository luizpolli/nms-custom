#!/usr/bin/env python3
"""Build the N540X-12Z16G-SYS-D chassis-view profile from EPNM assets.

Component data is sourced from the existing ncs540 profile (which was built
from real SNMP walk data of an N540X-12Z16G-SYS-D device).  Only the SVG
assets and hotspot coordinates are updated to use the real EPNM images.

Physical layout derived from:
- EPNM front SVG viewBox (1680x168)
- EPNM data JSON slot definitions (slots.x / slots.y anchors)
- SVG rect analysis of N540X-12Z16G-SYS-D_Front_core.svg:
    - PSU slot rect: x=206.5, y=61.5, w=206, h=65  → two side-by-side PSUs
    - RP slot: x=518, y=4, w=1088, h=154            → RSP SVG native size
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
FRONT_SVG = EPNM_ROOT / "Cisco_NCS_540X-12Z16G-SYS-D_Router" / "images" / "N540X-12Z16G-SYS-D_Front_core.svg"
MODULE_SVGS = {
    "N540X-12Z16G-SYS-D": EPNM_ROOT / "pluggables" / "images" / "horizontal" / "N540X-12Z16G-SYS-D_RSP.svg",
    "N540-PSU-FIXED-D":   EPNM_ROOT / "pluggables" / "images" / "horizontal" / "N540X-12Z16G-SYS-D_Front_depowersupply.svg",
}

BACKEND_OUT  = REPO_ROOT / "backend"  / "app" / "data" / "chassis" / "ncs540-12z16g"
FRONTEND_OUT = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs540-12z16g"

CANVAS_WIDTH  = 1680
CANVAS_HEIGHT = 168
FRONT_SVG_NAME = "NCS540-12Z16G-Front.svg"
PROFILE_ID = "Cisco_NCS_540X-12Z16G-SYS-D"
PLATFORM   = "Cisco NCS 540 (N540X-12Z16G-SYS-D)"
DEVICE_ID  = "example-ncs540-12z16g"


def hotspot(
    comp: dict[str, Any],
    hid: str,
    bounds: tuple[int, int, int, int],
    asset_typeid: str | None,
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
            "modelName":    comp.get("modelName"),
            "modelTypeId":  comp.get("modelName"),
            "sourceName":   comp.get("name"),
            "sourceTypeId": comp.get("modelName"),
        },
    }
    if asset_typeid:
        rel = f"/chassis-assets/ncs540-12z16g/modules/{asset_typeid}.svg"
        out["asset"] = {"typeId": asset_typeid, "image": rel, "sourceImage": rel}
    return out


def build() -> None:
    # Load component data from existing ncs540 profile
    src = json.loads(COMPONENT_SOURCE.read_text(encoding="utf-8"))
    components: dict[str, Any] = src["componentsById"]
    by_idx: dict[int, dict[str, Any]] = {c["physicalIndex"]: c for c in components.values()}

    # Key physical indices (same device as existing ncs540 profile — N540X-12Z16G-SYS-D)
    rp   = by_idx[1]      # 0/RP0/CPU0  — N540X-12Z16G-SYS-D
    pm0  = by_idx[8982]   # 0/PM0       — N540-PSU-FIXED-D
    pm1  = by_idx[13078]  # 0/PM1       — N540-PSU-FIXED-D

    # Hotspot bounds derived from SVG analysis:
    #   - RP:   x=518, y=4,  w=1088, h=154  (RSP SVG native size, EPNM slot x=518)
    #   - PSU slot rect in SVG: x=207, y=62, w=206, h=65
    #     Split evenly for PM0 (left half) and PM1 (right half)
    psu_w = 103
    hotspots = [
        hotspot(rp,  "hotspot-rp-1",          (518,  4,  1088, 154), "N540X-12Z16G-SYS-D"),
        hotspot(pm0, "hotspot-power-8982",     (207,  62, psu_w, 65), "N540-PSU-FIXED-D"),
        hotspot(pm1, "hotspot-power-13078",    (310,  62, psu_w, 65), "N540-PSU-FIXED-D"),
    ]

    profile = {
        "schemaVersion": "nms.chassisView.v1",
        "profileId": PROFILE_ID,
        "deviceId": DEVICE_ID,
        "platform": PLATFORM,
        "generatedAt": _dt.datetime.now(_tz.utc).isoformat(),
        "source": {
            "profile": "docs/snmpwalks/normalized/ncs540-entity-mib.json",
            "type": "entity-mib-derived-static-profile",
            "epnmSvg": "NCS540L_CE/Cisco_NCS_540X-12Z16G-SYS-D_Router/images/N540X-12Z16G-SYS-D_Front_core.svg",
            "note": "Component data reused from ncs540 profile (same device — N540X-12Z16G-SYS-D); EPNM SVG updated.",
        },
        "componentsById": components,
        "physicalIndexToComponentId": src.get("physicalIndexToComponentId", {}),
        "tree": src.get("tree", []),
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": f"/chassis-assets/ncs540-12z16g/{FRONT_SVG_NAME}",
                "width": CANVAS_WIDTH,
                "height": CANVAS_HEIGHT,
                "sourceWidth":  1670,
                "sourceHeight": 165,
                "hotspots": hotspots,
            }
        ],
    }

    for out_dir in (BACKEND_OUT, FRONTEND_OUT):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "modules").mkdir(exist_ok=True)
        shutil.copyfile(FRONT_SVG, out_dir / FRONT_SVG_NAME)
        for type_id, src_path in MODULE_SVGS.items():
            shutil.copyfile(src_path, out_dir / "modules" / f"{type_id}.svg")
        (out_dir / "normalized.json").write_text(
            json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {out_dir / 'normalized.json'}")


if __name__ == "__main__":
    build()
