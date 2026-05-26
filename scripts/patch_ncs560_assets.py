#!/usr/bin/env python3
"""Patch NCS560 normalized.json: populate hotspot.asset using each module's
real EPNM SVG (looked up by componentsById[inventoryId].modelName), with a
filler fallback when the real SVG isn't available."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs560" / "normalized.json"
FRONTEND_PUBLIC = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs560" / "normalized.json"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "chassis-assets" / "ncs560" / "normalized.json"

MODULES_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs560" / "modules"
MODULE_BASE = "/chassis-assets/ncs560/modules"

KIND_FILLER = {
    "rp": "NCS560-4-FILLER-RSP.svg",
    "linecard": "NCS560-FILLER-LC.svg",
    "power": "NCS560-FILLER-PT.svg",
}

FAN_PWR = "N560-4-PWR-FAN_Filler.svg"
FAN_HIGH = "N560-4-FAN-H_Filler.svg"


def available_svgs() -> set[str]:
    return {p.name for p in MODULES_DIR.glob("*.svg")}


def filler_for(kind: str, label: str) -> str | None:
    if kind == "fan":
        return FAN_PWR if label.endswith("0") else FAN_HIGH
    return KIND_FILLER.get(kind)


def pick_filename(kind: str, label: str, model_name: str | None, svgs: set[str]) -> str | None:
    if model_name:
        candidate = f"{model_name}.svg"
        if candidate in svgs:
            return candidate
    return filler_for(kind, label)


def patch(path: Path, svgs: set[str]) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comps = data.get("componentsById", {})
    real = 0
    filler = 0
    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            parts = hs["id"].split("-")
            kind = parts[1] if len(parts) > 1 else ""
            if kind not in {"rp", "linecard", "power", "fan"}:
                continue
            inv = hs.get("inventoryId")
            model_name = (comps.get(inv) or {}).get("modelName") if inv else None
            filename = pick_filename(kind, hs.get("label", ""), model_name, svgs)
            if not filename:
                continue
            if model_name and filename == f"{model_name}.svg":
                type_id = model_name
                real += 1
            else:
                type_id = filename.removesuffix(".svg")
                filler += 1
            hs["asset"] = {
                "typeId": type_id,
                "image": f"{MODULE_BASE}/{filename}",
                "sourceImage": f"{MODULE_BASE}/{filename}",
            }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return real, filler


def main() -> None:
    svgs = available_svgs()
    print(f"available SVGs in modules dir: {len(svgs)}")
    for path in (BACKEND, FRONTEND_PUBLIC, FRONTEND_DIST):
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        real, filler = patch(path, svgs)
        print(f"{path.relative_to(REPO_ROOT)}: real={real} filler={filler}")


if __name__ == "__main__":
    main()
