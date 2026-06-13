#!/usr/bin/env python3
"""Calibrate ASR920 chassis hotspots against the real EPNM front artwork.

Each profile pulls a different EPNM faceplate. Hotspot positions are expressed as
percentages of the artwork width/height (read visually against the rendered SVG)
and converted to absolute bounds. Tweak the LAYOUTS table and re-run.

Writes both the frontend (public/chassis-assets) and backend (app/data/chassis)
copies of each profile's normalized.json.

Profiles
--------
asr920-12cz     : 12CZ-D. Fan+2 PSU left; 8 RJ45 (left cage, 4 cols x 2 rows);
                  4 SFP-GE (right cage); 2x 10G uplink; viewBox 3422.5x312.5.
asr920-12sz     : 12SZ-D. Fan+2 PSU (DC terminal block) left; 12 SFP-GE/10G ports
                  in a single row inside the "1G/10G" cage right; viewBox 1680x166.

12SZ-IM is intentionally absent: its EPNM faceplate is a modular timing chassis
(GNSS / 10MHz / 1PPS, "10G SFP+" + "1G SFP" port groups numbered 15->0, IM bays)
whose layout does not map cleanly onto the inventory model, so that profile keeps
its construction-aligned synthetic faceplate until a dedicated calibration pass.
"""
from __future__ import annotations

import json
from pathlib import Path

# (x_center_pct, y_center_pct, w_pct, h_pct) per hotspot id.
LAYOUTS: dict[str, dict[str, tuple[float, float, float, float]]] = {}

# --------------------------------------------------------------------------- #
# ASR920-12CZ-D                                                               #
# --------------------------------------------------------------------------- #
_PW, _PH = 1.8, 20.0
_UW, _UH = 2.4, 24.0
_PSW, _PSH = 7.6, 42.0
_TOP, _BOT, _MID = 33.0, 55.0, 47.0
LAYOUTS["asr920-12cz"] = {
    # RJ45 0-7: left cage, 4 columns of vertical pairs (even=top, odd=bottom)
    "hotspot-rj45-0": (46.4, _TOP, _PW, _PH),
    "hotspot-rj45-1": (46.4, _BOT, _PW, _PH),
    "hotspot-rj45-2": (49.6, _TOP, _PW, _PH),
    "hotspot-rj45-3": (49.6, _BOT, _PW, _PH),
    "hotspot-rj45-4": (52.8, _TOP, _PW, _PH),
    "hotspot-rj45-5": (52.8, _BOT, _PW, _PH),
    "hotspot-rj45-6": (56.0, _TOP, _PW, _PH),
    "hotspot-rj45-7": (56.0, _BOT, _PW, _PH),
    # SFP-GE 8-11: right SFP cage (labels 8X/9X, 10X/11X)
    "hotspot-sfp-8": (72.5, _TOP, _PW, _PH),
    "hotspot-sfp-9": (72.5, _BOT, _PW, _PH),
    "hotspot-sfp-10": (75.7, _TOP, _PW, _PH),
    "hotspot-sfp-11": (75.7, _BOT, _PW, _PH),
    # 10G uplinks 12-13
    "hotspot-uplink-12": (80.5, _TOP, _UW, _UH),
    "hotspot-uplink-13": (80.5, _BOT, _UW, _UH),
    # Power supplies + fan (left)
    "hotspot-psu-0": (13.0, _MID, _PSW, _PSH),
    "hotspot-psu-1": (22.5, _MID, _PSW, _PSH),
    "hotspot-fan-0": (4.5, _MID, 6.0, 48.0),
}

# --------------------------------------------------------------------------- #
# ASR920-12SZ-D : 12 SFP ports in a single row inside the "1G/10G" cage        #
# --------------------------------------------------------------------------- #
_SZ_W, _SZ_H = 1.3, 42.0          # SFP port box
_SZ_Y = 47.0                      # single row, centred in the cage
# 12 evenly-spaced port x-centres (measured 71.4 .. 89.3, step ~1.63%)
_SZ_X = [71.4, 73.0, 74.8, 76.4, 78.0, 79.6, 81.3, 82.9, 84.5, 86.1, 87.8, 89.3]
LAYOUTS["asr920-12sz"] = {
    **{f"hotspot-sfp-{i}": (_SZ_X[i], _SZ_Y, _SZ_W, _SZ_H) for i in range(12)},
    "hotspot-psu-0": (11.0, 28.0, 7.5, 34.0),
    "hotspot-psu-1": (19.5, 28.0, 7.5, 34.0),
    "hotspot-fan-0": (3.5, 40.0, 5.5, 55.0),
}


def bounds(xc: float, yc: float, w: float, h: float, W: float, H: float) -> dict:
    bw = w / 100 * W
    bh = h / 100 * H
    return {
        "x": round(xc / 100 * W - bw / 2, 1),
        "y": round(yc / 100 * H - bh / 2, 1),
        "w": round(bw, 1),
        "h": round(bh, 1),
    }


def apply(repo: Path, profile: str, layout: dict) -> None:
    for base in ("frontend/public/chassis-assets", "backend/app/data/chassis"):
        path = repo / base / profile / "normalized.json"
        data = json.loads(path.read_text())
        view = data["views"][0]
        W, H = view["width"], view["height"]
        n = 0
        for hs in view["hotspots"]:
            spec = layout.get(hs["id"])
            if spec is None:
                continue
            hs["bounds"] = bounds(*spec, W, H)
            n += 1
        path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"{base}/{profile}: rewrote {n} hotspots")


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    for profile, layout in LAYOUTS.items():
        apply(repo, profile, layout)


if __name__ == "__main__":
    main()
