#!/usr/bin/env python3
"""Build the N540X-16Z4G8Q2C-D chassis-view profile from real EPNM assets + SNMP walk."""

from __future__ import annotations

import json
import shutil
import datetime as _dt
from datetime import timezone as _tz
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WALK_JSON = REPO_ROOT / "docs" / "snmpwalks" / "normalized" / "ncs540-16z4-entity-mib.json"
EPNM_ROOT = (
    REPO_ROOT
    / "docs"
    / "chassisview_figures"
    / "chassisview"
    / "com.cisco.prime.deviceprofile"
    / "NCS540L_CE"
)
FRONT_SVG = EPNM_ROOT / "Cisco_NCS_540X-16Z4G8Q2C-D_Router" / "images" / "N540X-16Z4G8Q2C-D_Front_core.svg"
MODULE_SVGS = {
    "N540-X-BB-FAN": EPNM_ROOT / "pluggables/images/horizontal/N540X-16Z4G8Q2C-A_Front_Fan.svg",
    "N540X-16Z4G8Q2C-D": EPNM_ROOT / "pluggables/images/horizontal/N540X-16Z4G8Q2C-D_RSP.svg",
    "N540-PSU-FIXED-D": EPNM_ROOT / "pluggables/images/horizontal/N540X-16Z4G8Q2C-D_front_dcpowersupply.svg",
}

BACKEND_OUT = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs540-16z4"
FRONTEND_OUT = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs540-16z4"

CANVAS_WIDTH = 1680
CANVAS_HEIGHT = 168
FRONT_SVG_NAME = "NCS540-16Z4-Front.svg"
PROFILE_ID = "Cisco_NCS_540X-16Z4G8Q2C-D"
PLATFORM = "Cisco NCS 540 (N540X-16Z4G8Q2C-D)"
DEVICE_ID = "example-ncs540-16z4"


def hotspot(comp: dict[str, Any], hid: str, kind: str, bounds: tuple[int, int, int, int], asset_typeid: str | None) -> dict[str, Any]:
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
        rel = f"/chassis-assets/ncs540-16z4/modules/{asset_typeid}.svg"
        out["asset"] = {"typeId": asset_typeid, "image": rel, "sourceImage": rel}
    return out


def build() -> None:
    walk = json.loads(WALK_JSON.read_text(encoding="utf-8"))
    components = walk["componentsById"]

    by_idx: dict[int, dict[str, Any]] = {c["physicalIndex"]: c for c in components.values()}

    fan = by_idx[4097]       # 0/FT0 — N540-X-BB-FAN
    rp = by_idx[1]           # 0/RP0/CPU0 — N540X-16Z4G8Q2C-D
    pm0 = by_idx[8983]       # 0/PM0 — N540-PSU-FIXED-D
    pm1 = by_idx[13079]      # 0/PM1 — N540-PSU-FIXED-D

    hotspots = [
        hotspot(fan, "hotspot-fan-4097", "fan", (24, 5, 198, 158), "N540-X-BB-FAN"),
        hotspot(rp, "hotspot-rp-1", "rp", (240, 12, 1056, 146), "N540X-16Z4G8Q2C-D"),
        # EPNM declares one PSU slot at x=1520; stacking PM0/PM1 vertically inside that footprint.
        hotspot(pm0, "hotspot-power-8983", "power", (1520, 15, 127, 74), "N540-PSU-FIXED-D"),
        hotspot(pm1, "hotspot-power-13079", "power", (1520, 91, 127, 74), "N540-PSU-FIXED-D"),
    ]

    profile = {
        "schemaVersion": "nms.chassisView.v1",
        "profileId": PROFILE_ID,
        "deviceId": DEVICE_ID,
        "platform": PLATFORM,
        "generatedAt": _dt.datetime.now(_tz.utc).isoformat(),
        "source": {
            "profile": "docs/snmpwalks/normalized/ncs540-16z4-entity-mib.json",
            "type": "entity-mib-derived-static-profile",
            "epnmSvg": "NCS540L_CE/Cisco_NCS_540X-16Z4G8Q2C-D_Router/images/N540X-16Z4G8Q2C-D_Front_core.svg",
        },
        "componentsById": components,
        "physicalIndexToComponentId": walk.get("physicalIndexToComponentId", {}),
        "tree": walk.get("tree", []),
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": f"/chassis-assets/ncs540-16z4/{FRONT_SVG_NAME}",
                "width": CANVAS_WIDTH,
                "height": CANVAS_HEIGHT,
                # sourceWidth/sourceHeight mirror the render canvas because
                # hotspot bounds are already expressed in CANVAS_WIDTH/HEIGHT
                # coordinates; the frontend percent layout divides by
                # view.width/height. Keep them aligned to avoid mismatch.
                "sourceWidth": CANVAS_WIDTH,
                "sourceHeight": CANVAS_HEIGHT,
                "hotspots": hotspots,
            }
        ],
    }

    for out_dir in (BACKEND_OUT, FRONTEND_OUT):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "modules").mkdir(exist_ok=True)
        shutil.copyfile(FRONT_SVG, out_dir / FRONT_SVG_NAME)
        for type_id, src in MODULE_SVGS.items():
            shutil.copyfile(src, out_dir / "modules" / f"{type_id}.svg")
        (out_dir / "normalized.json").write_text(
            json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote {out_dir / 'normalized.json'}")


if __name__ == "__main__":
    build()
