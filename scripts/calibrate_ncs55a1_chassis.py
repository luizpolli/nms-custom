"""
Calibrate chassis hotspot positions for NCS55A1 variants.

Inserts per-port hotspot entries derived from LED indicator positions in the
EPNM SVG artwork. Unlike calibrate_asr920_chassis.py (which updates existing
hotspot bounds), this script inserts new port hotspot entries and relocates the
chassis/rp0 background hotspots to the end of the array.

Derived from SVG LED extraction:
  48Q6H / 24Q6H  (viewBox 1670×165, 109 LEDs, pitch 13.2px):
    port_i center_x = 197.3 + i * 26.4  (54 ports: 48 QSFP28 + 6 SFP+)
  24H            (viewBox 1661×165, 113 LEDs, pitch 13.2px):
    port_i center_x = 134.7 + i * 26.4  (56 ports: 48 QSFP28 + 8 SFP+)
"""

import json
import shutil
from pathlib import Path

REPO = Path(__file__).parent.parent

FRONTEND_ASSETS = REPO / "frontend/public/chassis-assets"
BACKEND_ASSETS = REPO / "backend/app/data/chassis"


def port_hotspot(i: int, cx: float, y: int, w: int, h: int,
                 port_type: str, profile_id: str, module_path: str) -> dict:
    label = f"{port_type} {i}"
    slot_key = f"{port_type} bay {i}"
    x = round(cx - w / 2)
    return {
        "bounds": {"h": h, "w": w, "x": x, "y": y},
        "empty": True,
        "id": f"hotspot-port-{i}",
        "inventoryId": None,
        "label": label,
        "metadata": {"sourceName": slot_key, "sourceTypeId": profile_id},
        "physicalIndex": None,
        "slotKey": slot_key,
        "asset": {
            "typeId": port_type,
            "image": module_path,
            "sourceImage": module_path,
        },
    }


# Profile definitions -----------------------------------------------------------
# Each profile: (port_count, center_x_formula, y, w, h, profile_id, module_path,
#                qsfp_count, sfp_count)
PROFILES = {
    "ncs55a1-48q6h": {
        "port_count": 54,
        "qsfp_count": 48,
        "sfp_count": 6,
        # LED pair center: first LED x=190.7, LED pitch=13.2 → port pitch=26.4
        # center_x = 190.7 + (2*i + 0.5) * 13.2 = 197.3 + i * 26.4
        "cx_start": 197.3,
        "cx_pitch": 26.4,
        "y": 29,
        "w": 24,
        "h": 102,
        "profile_id": "NCS-55A1-48Q6H",
        "module_path": "/chassis-assets/ncs55a1/modules/QSFP.svg",
    },
    "ncs55a1-24q6h": {
        "port_count": 54,
        "qsfp_count": 48,   # SVG is identical to 48Q6H; slots match LED pairs
        "sfp_count": 6,
        "cx_start": 197.3,
        "cx_pitch": 26.4,
        "y": 29,
        "w": 24,
        "h": 102,
        "profile_id": "NCS-55A1-24Q6H-S",
        "module_path": "/chassis-assets/ncs55a1/modules/QSFP.svg",
    },
    "ncs55a1-24h": {
        "port_count": 56,
        "qsfp_count": 48,
        "sfp_count": 8,
        # LED pair center: first LED x=128.1, LED pitch≈13.2 → port pitch=26.4
        # center_x = 128.1 + (2*i + 0.5) * 13.2 = 134.7 + i * 26.4
        "cx_start": 134.7,
        "cx_pitch": 26.4,
        "y": 27,
        "w": 24,
        "h": 103,
        "profile_id": "NCS-55A1-24H",
        "module_path": "/chassis-assets/ncs55a1/modules/QSFP.svg",
    },
}


def build_port_hotspots(cfg: dict) -> list[dict]:
    hotspots = []
    qsfp = cfg["qsfp_count"]
    sfp = cfg["sfp_count"]
    for i in range(cfg["port_count"]):
        cx = cfg["cx_start"] + i * cfg["cx_pitch"]
        if i < qsfp:
            ptype = "QSFP28"
        else:
            ptype = "SFP+"
        hotspots.append(
            port_hotspot(
                i=i,
                cx=cx,
                y=cfg["y"],
                w=cfg["w"],
                h=cfg["h"],
                port_type=ptype,
                profile_id=cfg["profile_id"],
                module_path=cfg["module_path"],
            )
        )
    return hotspots


def apply(profile: str, cfg: dict, dry_run: bool = False) -> None:
    paths = [
        FRONTEND_ASSETS / profile / "normalized.json",
        BACKEND_ASSETS / profile / "normalized.json",
    ]

    for p in paths:
        if not p.exists():
            print(f"  SKIP (missing): {p}")
            continue

        with open(p) as f:
            data = json.load(f)

        view = data["views"][0]
        existing = view["hotspots"]

        # Separate background hotspots (chassis, rp0) from any port hotspots
        background_ids = {"hotspot-chassis", "hotspot-rp0"}
        background = [h for h in existing if h["id"] in background_ids]
        # Drop any previous port hotspots (hotspot-port-*)
        # and keep non-background, non-port hotspots if any exist
        other = [h for h in existing if h["id"] not in background_ids
                 and not h["id"].startswith("hotspot-port-")]

        port_hotspots = build_port_hotspots(cfg)

        # Order: specific port hotspots first, then other module hotspots,
        # then background last (disabled → pointer-events:none → lets clicks through)
        view["hotspots"] = port_hotspots + other + background

        if dry_run:
            print(f"  [DRY RUN] would write {len(view['hotspots'])} hotspots → {p}")
            continue

        p.write_text(json.dumps(data, indent=2))
        print(f"  wrote {len(port_hotspots)} port hotspots → {p.relative_to(REPO)}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Calibrate NCS55A1 chassis hotspots")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("profiles", nargs="*", default=list(PROFILES.keys()))
    args = parser.parse_args()

    for profile in args.profiles:
        if profile not in PROFILES:
            print(f"Unknown profile: {profile}. Valid: {list(PROFILES.keys())}")
            continue
        print(f"\n{profile}:")
        apply(profile, PROFILES[profile], dry_run=args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
