#!/usr/bin/env python3
"""Patch NCS540 (N540X-12Z16G-SYS-D) and ASR-920-20SZ-M normalized.json:
populate hotspot.asset using EPNM SVGs.

Mirrors the approach already used by patch_ncs560_assets.py and
patch_ncs55a1_assets.py: per-PID SVGs when EPNM ships them, generic
SFP/QSFP/GLC for optic bays (EPNM has no per-PID optic SVGs), chassis
backplate stays unset.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Generic optic SVGs (imported from NCS540L_CE & NCS42XX pluggables).
GENERIC_SFP = "SFP.svg"
GENERIC_QSFP = "QSFP.svg"
GENERIC_GLC = "GLC.svg"


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


# ---------------- NCS540 (N540X-12Z16G-SYS-D) ----------------

NCS540_BACKEND = REPO_ROOT / "backend/app/data/chassis/ncs540/normalized.json"
NCS540_FE = REPO_ROOT / "frontend/public/chassis-assets/ncs540/normalized.json"
NCS540_DIST = REPO_ROOT / "frontend/dist/chassis-assets/ncs540/normalized.json"
NCS540_MODULE_BASE = "/chassis-assets/ncs540/modules"

NCS540_RP_SVG = "N540X-12Z16G-SYS-D_RSP.svg"
NCS540_PSU_SVG = "N540X-12Z16G-SYS-D_Front_depowersupply.svg"


def patch_ncs540(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comps = data.get("componentsById", {})
    stats = {"real": 0, "filler": 0, "skipped": 0, "rewritten": 0}

    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            hid = hs["id"]
            slot_key = hs.get("slotKey", "") or ""
            inv_id = hs.get("inventoryId")
            inv = (comps.get(inv_id) or {}) if inv_id else {}
            inv_model = inv.get("modelName")
            if inv_model == "N/A":
                inv_model = None

            filename: str | None = None
            type_id: str | None = None
            tier = "filler"

            if hid.startswith("hotspot-bay"):
                child_model = first_child_transceiver_model(comps, inv_id)
                filename = pick_transceiver_filename(child_model, slot_key)
                if child_model:
                    type_id = child_model
                    tier = "real"
                else:
                    type_id = filename.removesuffix(".svg")
            elif hid.startswith("hotspot-rp"):
                filename = NCS540_RP_SVG
                type_id = inv_model or "N540X-12Z16G-SYS-D-RSP"
                tier = "real" if inv_model else "filler"
            elif hid.startswith("hotspot-power"):
                # Already has an asset but pointing to wrong variant
                # (N540X-16Z8Q2C-D); rewrite to 12Z16G-SYS-D.
                filename = NCS540_PSU_SVG
                type_id = inv_model or "N540-PSU-FIXED-D"
                tier = "real" if inv_model else "filler"
                if hs.get("asset"):
                    stats["rewritten"] += 1
            elif hid.startswith("hotspot-fan"):
                # Already populated with the 24Q8L2DD rear-fan SVG, which is
                # close enough; leave as-is.
                stats["skipped"] += 1
                continue
            elif hid.startswith("hotspot-chassis"):
                stats["skipped"] += 1
                continue
            else:
                stats["skipped"] += 1
                continue

            hs["asset"] = {
                "typeId": type_id,
                "image": f"{NCS540_MODULE_BASE}/{filename}",
                "sourceImage": f"{NCS540_MODULE_BASE}/{filename}",
            }
            if tier == "real":
                stats["real"] += 1
            else:
                stats["filler"] += 1

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return stats


# ---------------- ASR-920-20SZ-M ----------------

ASR920_BACKEND = REPO_ROOT / "backend/app/data/chassis/asr920/normalized.json"
ASR920_FE = REPO_ROOT / "frontend/public/chassis-assets/asr920/normalized.json"
ASR920_DIST = REPO_ROOT / "frontend/dist/chassis-assets/asr920/normalized.json"
ASR920_MODULE_BASE = "/chassis-assets/asr920/modules"

ASR920_PSU_AC = "ASR-920-PWR-A.svg"
ASR920_PSU_DC = "ASR-920-PWR-D.svg"
ASR920_PSU_FILLER = "ASR-920-PWR-FILLER.svg"


def patch_asr920(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    comps = data.get("componentsById", {})
    stats = {"real": 0, "filler": 0, "skipped": 0}

    for view in data.get("views", []):
        for hs in view.get("hotspots", []):
            hid = hs["id"]
            slot_key = hs.get("slotKey", "") or ""
            inv_id = hs.get("inventoryId")
            inv = (comps.get(inv_id) or {}) if inv_id else {}
            inv_model = inv.get("modelName")
            inv_desc = (inv.get("description") or "")
            if inv_model == "N/A":
                inv_model = None

            filename: str | None = None
            type_id: str | None = None
            tier = "filler"

            if hid.startswith("hotspot-sfp") or hid.startswith("hotspot-uplink"):
                child_model = first_child_transceiver_model(comps, inv_id)
                filename = pick_transceiver_filename(child_model, slot_key)
                if child_model:
                    type_id = child_model
                    tier = "real"
                else:
                    # Empty bay — use port-type as typeId hint.
                    if hid.startswith("hotspot-uplink"):
                        type_id = "SFP+"
                    else:
                        type_id = "SFP"
            elif hid.startswith("hotspot-psu"):
                # PSU description like "ASR 920 250W AC Power Supply"
                if "AC" in inv_desc.upper():
                    filename = ASR920_PSU_AC
                    type_id = "ASR-920-PWR-A"
                elif "DC" in inv_desc.upper():
                    filename = ASR920_PSU_DC
                    type_id = "ASR-920-PWR-D"
                else:
                    filename = ASR920_PSU_FILLER
                    type_id = "ASR-920-PWR-FILLER"
                tier = "real"
            elif hid.startswith("hotspot-mgmt"):
                # MGMT port: embedded in base SVG; skip.
                stats["skipped"] += 1
                continue
            else:
                stats["skipped"] += 1
                continue

            if not filename:
                stats["skipped"] += 1
                continue

            hs["asset"] = {
                "typeId": type_id,
                "image": f"{ASR920_MODULE_BASE}/{filename}",
                "sourceImage": f"{ASR920_MODULE_BASE}/{filename}",
            }
            if tier == "real":
                stats["real"] += 1
            else:
                stats["filler"] += 1

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    print("== NCS540 (N540X-12Z16G-SYS-D) ==")
    for p in (NCS540_BACKEND, NCS540_FE, NCS540_DIST):
        if not p.exists():
            print(f"  SKIP missing: {p}")
            continue
        s = patch_ncs540(p)
        print(f"  {p.relative_to(REPO_ROOT)}: {s}")

    print("\n== ASR-920-20SZ-M ==")
    for p in (ASR920_BACKEND, ASR920_FE, ASR920_DIST):
        if not p.exists():
            print(f"  SKIP missing: {p}")
            continue
        s = patch_asr920(p)
        print(f"  {p.relative_to(REPO_ROOT)}: {s}")


if __name__ == "__main__":
    main()
