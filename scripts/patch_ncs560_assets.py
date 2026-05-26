#!/usr/bin/env python3
"""Patch NCS560 normalized.json to populate hotspot.asset with EPNM filler SVGs."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs560" / "normalized.json"
FRONTEND_PUBLIC = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs560" / "normalized.json"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "chassis-assets" / "ncs560" / "normalized.json"

MODULE_BASE = "/chassis-assets/ncs560/modules"

KIND_TO_FILLER = {
    "rp": ("NCS560-4-FILLER-RSP", "NCS560-4-FILLER-RSP.svg"),
    "linecard": ("NCS560-FILLER-LC", "NCS560-FILLER-LC.svg"),
    "power": ("NCS560-FILLER-PT", "NCS560-FILLER-PT.svg"),
}


def fan_filler(label: str) -> tuple[str, str]:
    if label.endswith("0"):
        return ("N560-4-PWR-FAN_Filler", "N560-4-PWR-FAN_Filler.svg")
    return ("N560-4-FAN-H_Filler", "N560-4-FAN-H_Filler.svg")


def kind_of(hotspot_id: str) -> str:
    return hotspot_id.split("-")[1] if "-" in hotspot_id else ""


def patch(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    touched = 0
    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            kind = kind_of(hs["id"])
            if kind == "fan":
                type_id, filename = fan_filler(hs.get("label", ""))
            elif kind in KIND_TO_FILLER:
                type_id, filename = KIND_TO_FILLER[kind]
            else:
                continue
            hs["asset"] = {
                "typeId": type_id,
                "image": f"{MODULE_BASE}/{filename}",
                "sourceImage": f"{MODULE_BASE}/{filename}",
            }
            touched += 1
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return touched


def main() -> None:
    for path in (BACKEND, FRONTEND_PUBLIC, FRONTEND_DIST):
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        n = patch(path)
        print(f"patched {n} hotspots in {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
