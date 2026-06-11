#!/usr/bin/env python3
"""Patch the static-profile stub chassis (ncs5501, ncs5502, ncs5508,
ncs55a1-24h, ncs55a1-24q6h, ncs55a1-48q6h) with EPNM SVG assets.

These six profiles ship 0 components and use slot-level hotspots only
(no per-port flattening), so the patcher just maps each hotspot id to
the appropriate EPNM SVG. Chassis backplate hotspots remain unset
because they're the base image.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def apply_mapping(name: str, mapping: dict[str, dict[str, str]]) -> dict[str, int]:
    """Apply asset mapping to backend + frontend public + dist json files.

    mapping: hotspot.id -> {"file": str, "typeId": str}
    """
    backend = REPO_ROOT / f"backend/app/data/chassis/{name}/normalized.json"
    fe = REPO_ROOT / f"frontend/public/chassis-assets/{name}/normalized.json"
    dist = REPO_ROOT / f"frontend/dist/chassis-assets/{name}/normalized.json"
    module_base = f"/chassis-assets/{name}/modules"

    total_real = 0
    total_skipped = 0
    for path in (backend, fe, dist):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for view in data.get("views", []):
            for hs in view.get("hotspots", []):
                hid = hs["id"]
                entry = mapping.get(hid)
                if not entry:
                    total_skipped += 1
                    continue
                filename = entry["file"]
                type_id = entry["typeId"]
                hs["asset"] = {
                    "typeId": type_id,
                    "image": f"{module_base}/{filename}",
                    "sourceImage": f"{module_base}/{filename}",
                }
                total_real += 1
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    # Divide by 3 because we touched 3 files identically.
    return {"populated_per_file": total_real // 3, "skipped_per_file": total_skipped // 3}


# ---- mappings per chassis ----


NCS5501 = {
    # Front (single fixed-port RP card).
    "hotspot-rp0": {"file": "NCS-5501_RP.svg", "typeId": "NCS-5501-RP"},
    # Rear.
    "hotspot-pm0": {"file": "NCS-5501_Rear_powersupply.svg", "typeId": "NCS-5501-PSU"},
    "hotspot-pm1": {"file": "NCS-5501_Rear_powersupply.svg", "typeId": "NCS-5501-PSU"},
    "hotspot-ft0": {"file": "NCS-5501_Rear_fan.svg", "typeId": "NCS-5501-FAN"},
    "hotspot-ft1": {"file": "NCS-5501_Rear_fan.svg", "typeId": "NCS-5501-FAN"},
    "hotspot-ft2": {"file": "NCS-5501_Rear_fan.svg", "typeId": "NCS-5501-FAN"},
}


NCS5502 = {
    "hotspot-rp0": {"file": "NCS-5502-RP.svg", "typeId": "NCS-5502-RP"},
    "hotspot-pm0": {"file": "NCS-5502-Rear-powersupply.svg", "typeId": "NCS-5502-PSU"},
    "hotspot-pm1": {"file": "NCS-5502-Rear-powersupply.svg", "typeId": "NCS-5502-PSU"},
    "hotspot-ft0": {"file": "NCS-5502-Rear-fan.svg", "typeId": "NCS-5502-FAN"},
    "hotspot-ft1": {"file": "NCS-5502-Rear-fan.svg", "typeId": "NCS-5502-FAN"},
    "hotspot-ft2": {"file": "NCS-5502-Rear-fan.svg", "typeId": "NCS-5502-FAN"},
}


NCS5508 = {
    # Line cards: use 36X100G as a representative LC artwork (most common).
    "hotspot-lc0": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc1": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc2": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc3": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc4": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc5": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc6": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    "hotspot-lc7": {"file": "NC55-36X100G.svg", "typeId": "NC55-36X100G"},
    # RPs
    "hotspot-rp0": {"file": "NC55-RP-E.svg", "typeId": "NC55-RP-E"},
    "hotspot-rp1": {"file": "NC55-RP-E.svg", "typeId": "NC55-RP-E"},
    # PSUs (1200W AC default; will be overridden when live SNMP arrives).
    "hotspot-pm0": {"file": "NC55-1200W-ACFW.svg", "typeId": "NC55-1200W-ACFW"},
    "hotspot-pm1": {"file": "NC55-1200W-ACFW.svg", "typeId": "NC55-1200W-ACFW"},
    "hotspot-pm2": {"file": "NC55-1200W-ACFW.svg", "typeId": "NC55-1200W-ACFW"},
    "hotspot-pm3": {"file": "NC55-1200W-ACFW.svg", "typeId": "NC55-1200W-ACFW"},
    # Rear
    "hotspot-ft0": {"file": "NS55-5508-FAN.svg", "typeId": "NS55-5508-FAN"},
    "hotspot-ft1": {"file": "NS55-5508-FAN.svg", "typeId": "NS55-5508-FAN"},
    "hotspot-ft2": {"file": "NS55-5508-FAN.svg", "typeId": "NS55-5508-FAN"},
    "hotspot-fc0": {"file": "NC55-5508-FC.svg", "typeId": "NC55-5508-FC"},
    "hotspot-fc1": {"file": "NC55-5508-FC.svg", "typeId": "NC55-5508-FC"},
    "hotspot-fc2": {"file": "NC55-5508-FC.svg", "typeId": "NC55-5508-FC"},
    "hotspot-fc3": {"file": "NC55-5508-FC.svg", "typeId": "NC55-5508-FC"},
    "hotspot-fc4": {"file": "NC55-5508-FC.svg", "typeId": "NC55-5508-FC"},
    "hotspot-sc0": {"file": "NC55-SC.svg", "typeId": "NC55-SC"},
    "hotspot-sc1": {"file": "NC55-SC.svg", "typeId": "NC55-SC"},
}


NCS55A1_24H = {
    "hotspot-rp0": {"file": "NCS-55A1-24H_Front_RP.svg", "typeId": "NCS-55A1-24H"},
    "hotspot-pm0": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-pm1": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-ft0": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft1": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft2": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
}

# 24Q6H-S and 48Q6H reuse the 36H-S RP look (their per-PID RP SVGs aren't
# in the EPNM pack we have).
NCS55A1_24Q6H = {
    "hotspot-rp0": {"file": "NCS-55A1-36H-S-RP.svg", "typeId": "NCS-55A1-24Q6H-S-RP"},
    "hotspot-pm0": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-pm1": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-ft0": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft1": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft2": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
}

NCS55A1_48Q6H = {
    "hotspot-rp0": {"file": "NCS-55A1-36H-S-RP.svg", "typeId": "NCS-55A1-48Q6H-RP"},
    "hotspot-pm0": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-pm1": {"file": "NC55-2KW-DCFW.svg", "typeId": "NC55-2KW-DCFW"},
    "hotspot-ft0": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft1": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
    "hotspot-ft2": {"file": "NC55-A1-FAN-FW.svg", "typeId": "NC55-A1-FAN-FW"},
}


CHASSIS = [
    ("ncs5501", NCS5501),
    ("ncs5502", NCS5502),
    ("ncs5508", NCS5508),
    ("ncs55a1-24h", NCS55A1_24H),
    ("ncs55a1-24q6h", NCS55A1_24Q6H),
    ("ncs55a1-48q6h", NCS55A1_48Q6H),
]


def main() -> None:
    for name, mapping in CHASSIS:
        stats = apply_mapping(name, mapping)
        print(f"  {name}: populated={stats['populated_per_file']} skipped={stats['skipped_per_file']}")


if __name__ == "__main__":
    main()
