#!/usr/bin/env python3
"""Patch NCS55A1 normalized.json: populate hotspot.asset for QSFP28 bays,
PSU slots, fan trays, and the fixed RP using EPNM SVGs (with fillers for
empty bays / missing pluggables).

Mirrors the approach used by patch_ncs560_assets.py: per-PID SVGs when
EPNM ships them, generic SFP/QSFP/GLC for optic bays (since EPNM has no
per-PID optic SVGs), and chassis backplate stays unset.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs55a1" / "normalized.json"
FRONTEND_PUBLIC = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs55a1" / "normalized.json"
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "chassis-assets" / "ncs55a1" / "normalized.json"

MODULES_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs55a1" / "modules"
MODULE_BASE = "/chassis-assets/ncs55a1/modules"

# Generic optic SVGs imported from NCS55XX_CE/pluggables.
GENERIC_SFP = "SFP.svg"
GENERIC_QSFP = "QSFP.svg"
GENERIC_GLC = "GLC.svg"

# Fillers for empty bays / missing PSU / missing fan.
PSU_FILLER = "NCS-55A1-36H-S-PWR-Filler.svg"
FAN_FILLER = "NCS-55A1-36H-S_Rear_FAN-Filler.svg"


def available_svgs() -> set[str]:
    return {p.name for p in MODULES_DIR.glob("*.svg")}


def pick_transceiver_filename(child_model: str | None, slot_label: str) -> str:
    if child_model:
        upper = child_model.upper()
        if upper.startswith("QSFP") or "-QSFP" in upper:
            return GENERIC_QSFP
        if upper.startswith("GLC"):
            return GENERIC_GLC
        if upper.startswith("SFP") or "-SFP" in upper:
            return GENERIC_SFP
    slot_upper = (slot_label or "").upper()
    if "QSFP" in slot_upper:
        return GENERIC_QSFP
    return GENERIC_SFP


def first_child_transceiver_model(comps: dict, inv_id: str | None) -> str | None:
    if not inv_id:
        return None
    bay = comps.get(inv_id) or {}
    for cid in bay.get("childIds", []) or []:
        child = comps.get(cid) or {}
        mn = child.get("modelName")
        if mn and mn != "N/A":
            return mn
    return None


def patch(path: Path, svgs: set[str]) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comps = data.get("componentsById", {})
    stats: dict[str, int] = {"real": 0, "filler": 0, "skipped": 0, "qsfp_empty": 0}

    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            hid = hs["id"]
            inv_id = hs.get("inventoryId")
            inv = (comps.get(inv_id) or {}) if inv_id else {}
            inv_model = inv.get("modelName")
            if inv_model == "N/A":
                inv_model = None
            slot_key = hs.get("slotKey", "") or ""

            filename: str | None = None
            type_id: str | None = None
            tier: str | None = None  # "real" | "filler"

            if hid.startswith("hotspot-qsfp"):
                # Pluggable optic bay
                child_model = first_child_transceiver_model(comps, inv_id)
                filename = pick_transceiver_filename(child_model, slot_key)
                if child_model:
                    type_id = child_model
                    tier = "real"
                else:
                    type_id = filename.removesuffix(".svg")
                    tier = "filler"
                    stats["qsfp_empty"] += 1
            elif "PM" in (slot_key.split("/")[-1] if "/" in slot_key else slot_key):
                # Power supply slot
                if inv_model and f"{inv_model}.svg" in svgs:
                    filename = f"{inv_model}.svg"
                    type_id = inv_model
                    tier = "real"
                else:
                    filename = PSU_FILLER
                    type_id = PSU_FILLER.removesuffix(".svg")
                    tier = "filler"
            elif "FT" in (slot_key.split("/")[-1] if "/" in slot_key else slot_key):
                # Fan tray slot
                if inv_model and f"{inv_model}.svg" in svgs:
                    filename = f"{inv_model}.svg"
                    type_id = inv_model
                    tier = "real"
                else:
                    filename = FAN_FILLER
                    type_id = FAN_FILLER.removesuffix(".svg")
                    tier = "filler"
            elif "/" in slot_key and slot_key.split("/")[-1].startswith("RP"):
                # Fixed RP hotspot (id like hotspot-1, slotKey "0/RP0")
                if inv_model == "NCS-55A1-36H-SE-S":
                    candidate = "NCS-55A1-36H-SE-S-RP.svg"
                    if candidate in svgs:
                        filename = candidate
                        type_id = "NCS-55A1-36H-SE-S-RP"
                        tier = "real"
            elif hid.startswith("hotspot-chassis") or hid.endswith("-rear") or "Rack" in slot_key:
                # Chassis backplate: leave without asset (matches NCS560).
                stats["skipped"] += 1
                continue
            else:
                # MGMT port etc. — embedded in the base SVG.
                stats["skipped"] += 1
                continue

            if not filename:
                stats["skipped"] += 1
                continue

            hs["asset"] = {
                "typeId": type_id,
                "image": f"{MODULE_BASE}/{filename}",
                "sourceImage": f"{MODULE_BASE}/{filename}",
            }
            if tier == "real":
                stats["real"] += 1
            else:
                stats["filler"] += 1

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    svgs = available_svgs()
    print(f"available SVGs in modules dir: {len(svgs)}")
    for path in (BACKEND, FRONTEND_PUBLIC, FRONTEND_DIST):
        if not path.exists():
            print(f"SKIP missing: {path}")
            continue
        stats = patch(path, svgs)
        print(
            f"{path.relative_to(REPO_ROOT)}: real={stats['real']} "
            f"filler={stats['filler']} skipped={stats['skipped']} "
            f"(empty bays={stats['qsfp_empty']})"
        )


if __name__ == "__main__":
    main()
