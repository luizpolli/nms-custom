#!/usr/bin/env python3
"""Patch NCS540 normalized.json: populate hotspot.asset for module-bearing
hotspots (rp/power/fan) using EPNM-derived SVG filenames per modelName.

Bays are fixed ports on the NCS540 chassis and intentionally carry no asset.
The chassis hotspot is covered by the front-view SVG and also carries no asset.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs540" / "normalized.json"
FRONTEND_PUBLIC = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs540" / "normalized.json"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "chassis-assets" / "ncs540" / "normalized.json"

MODULES_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs540" / "modules"
MODULE_BASE = "/chassis-assets/ncs540/modules"

# EPNM pluggables.json -> svgImageId mappings for N540X-12Z16G-SYS-D
MODEL_SVG: dict[str, str] = {
    "N540-PSU-FIXED-D": "N540X-16Z8Q2C-D_front_dcpowersupply.svg",
    "N540-FAN": "N540-24Q8L2DD-SYS_rear_fans.svg",
}

# Hotspot kinds that get module assets. Bays are ports; chassis is the front SVG.
ASSET_KINDS = {"rp", "power", "fan"}


def patch(path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comps = data.get("componentsById", {})
    real = 0
    skipped = 0
    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            parts = hs["id"].split("-")
            kind = parts[1] if len(parts) > 1 else ""
            if kind not in ASSET_KINDS:
                continue
            inv = hs.get("inventoryId")
            model_name = (comps.get(inv) or {}).get("modelName") if inv else None
            svg = MODEL_SVG.get(model_name) if model_name else None
            if not svg:
                skipped += 1
                continue
            hs["asset"] = {
                "typeId": model_name,
                "image": f"{MODULE_BASE}/{svg}",
                "sourceImage": f"{MODULE_BASE}/{svg}",
            }
            real += 1
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return real, skipped


def main() -> None:
    for path in (BACKEND, FRONTEND_PUBLIC, FRONTEND_DIST):
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        real, skipped = patch(path)
        print(f"{path.relative_to(REPO_ROOT)}: real={real} skipped={skipped}")


if __name__ == "__main__":
    main()
