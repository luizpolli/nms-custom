#!/usr/bin/env python3
"""Patch NCS540 variant normalized.json files (ncs540-fh-agg, ncs540-fh-csr,
ncs540x-4z14g2q) with EPNM SVG assets.

Same approach as patch_ncs540_asr920_assets.py: route hotspots to per-PID
SVGs when EPNM has them, otherwise to family-generic fallbacks.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def first_child_modelname(comps: dict, inv_id: str | None) -> str | None:
    if not inv_id:
        return None
    bay = comps.get(inv_id) or {}
    for cid in bay.get("childIds", []) or []:
        child = comps.get(cid) or {}
        mn = child.get("modelName")
        if mn and mn != "N/A":
            return mn
    return None


def patch_variant(
    name: str,
    *,
    rp_svg: str,
    psu_svg: str,
    fan_svg: str | None,
) -> dict[str, int]:
    """Generic patcher for a fixed-port NCS540 variant.

    Each variant has the same 3-4 top-level hotspots (RP, PM0, PM1,
    optional FT0).  No SFP bays at this level (they're embedded in the
    RP SVG image).
    """
    backend = REPO_ROOT / f"backend/app/data/chassis/{name}/normalized.json"
    fe = REPO_ROOT / f"frontend/public/chassis-assets/{name}/normalized.json"
    dist = REPO_ROOT / f"frontend/dist/chassis-assets/{name}/normalized.json"
    module_base = f"/chassis-assets/{name}/modules"

    stats = {"real": 0, "filler": 0, "skipped": 0}

    for path in (backend, fe, dist):
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        comps = data.get("componentsById", {})
        for view in data.get("views", []):
            for hs in view.get("hotspots", []):
                hid = hs["id"]
                inv_id = hs.get("inventoryId")
                inv = (comps.get(inv_id) or {}) if inv_id else {}
                inv_model = inv.get("modelName")
                if inv_model == "N/A":
                    inv_model = None

                filename: str | None = None
                type_id: str | None = None

                if hid.startswith("hotspot-rp"):
                    filename = rp_svg
                    type_id = inv_model or rp_svg.removesuffix(".svg")
                elif hid.startswith("hotspot-power"):
                    filename = psu_svg
                    type_id = inv_model or psu_svg.removesuffix(".svg")
                elif hid.startswith("hotspot-fan"):
                    if fan_svg is None:
                        stats["skipped"] += 1
                        continue
                    filename = fan_svg
                    type_id = inv_model or fan_svg.removesuffix(".svg")
                else:
                    stats["skipped"] += 1
                    continue

                hs["asset"] = {
                    "typeId": type_id,
                    "image": f"{module_base}/{filename}",
                    "sourceImage": f"{module_base}/{filename}",
                }
                stats["real"] += 1 if inv_model else 0
                stats["filler"] += 0 if inv_model else 1
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    return stats


VARIANTS = [
    {
        "name": "ncs540-fh-agg",
        "rp_svg": "N540-FH-AGG-SYS_Front_Ports.svg",
        "psu_svg": "N540-FH-AGG-SYS_Power_Module-DC.svg",
        "fan_svg": "N540-FH-AGG-SYS_Fan.svg",
    },
    {
        "name": "ncs540-fh-csr",
        # CSR has its own front-port image but no per-PID fan/PSU; reuse AGG's.
        "rp_svg": "N540-FH-CSR-SYS_Front_Port.svg",
        "psu_svg": "N540-FH-AGG-SYS_Power_Module-DC.svg",
        "fan_svg": "N540-FH-AGG-SYS_Fan.svg",
    },
    {
        "name": "ncs540x-4z14g2q",
        "rp_svg": "N540X-4Z14G2Q_front_ports.svg",
        # 4Z14G2Q-D doesn't have its own PSU SVG in EPNM; reuse the
        # 12Z16G-SYS-D DC PSU which is the same N540-PSU-FIXED-D part.
        "psu_svg": "N540X-12Z16G-SYS-D_Front_depowersupply.svg",
        # 4Z14G2Q-D normalized.json has no fan hotspot at the top level.
        "fan_svg": None,
    },
]


def main() -> None:
    for v in VARIANTS:
        stats = patch_variant(**v)
        print(f"  {v['name']}: {stats}")


if __name__ == "__main__":
    main()
