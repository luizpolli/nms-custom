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

# Generic pluggable SVGs (sourced from EPNM NCS55XX_CE/pluggables) used when no
# per-model SVG exists. We never get per-model SVGs for SFP/QSFP/GLC optics from
# EPNM, so we route by transceiver family heuristics.
GENERIC_SFP = "SFP.svg"
GENERIC_QSFP = "QSFP.svg"
GENERIC_GLC = "GLC.svg"


def pick_transceiver_filename(child_model: str | None, slot_label: str) -> str:
    """Map a child transceiver modelName to the best generic SVG."""
    if child_model:
        upper = child_model.upper()
        if upper.startswith("QSFP") or "-QSFP" in upper:
            return GENERIC_QSFP
        if upper.startswith("GLC"):
            return GENERIC_GLC
        if upper.startswith("SFP") or "-SFP" in upper:
            return GENERIC_SFP
    # Fall back to slotKey hint ("QSFP bay 0", "SFP bay 0", ...).
    slot_upper = (slot_label or "").upper()
    if "QSFP" in slot_upper:
        return GENERIC_QSFP
    return GENERIC_SFP


def first_child_transceiver_model(comps: dict, inv_id: str | None) -> str | None:
    """Bay containers hold a pluggable module child; return its modelName."""
    if not inv_id:
        return None
    bay = comps.get(inv_id) or {}
    for cid in bay.get("childIds", []) or []:
        child = comps.get(cid) or {}
        mn = child.get("modelName")
        if mn and mn != "N/A":
            return mn
    return None


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
            if kind not in {"rp", "linecard", "power", "fan", "bay"}:
                continue
            inv = hs.get("inventoryId")
            model_name = (comps.get(inv) or {}).get("modelName") if inv else None
            if model_name == "N/A":
                model_name = None
            if kind == "bay":
                # Bays are pluggable containers; resolve by their child
                # transceiver modelName, but always render with the EPNM
                # generic SFP/QSFP/GLC SVG since per-PID optics SVGs
                # don't exist in the asset pack.
                child_model = first_child_transceiver_model(comps, inv)
                filename = pick_transceiver_filename(child_model, hs.get("slotKey", ""))
                type_id = (child_model or filename.removesuffix(".svg"))
                if child_model:
                    real += 1
                else:
                    filler += 1
            else:
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
