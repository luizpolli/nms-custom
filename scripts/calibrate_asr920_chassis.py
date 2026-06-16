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
asr920-12sz-im  : 12SZ-IM-CC modular timing chassis; ports descending 15->0
                  (10G-SFP+ uplinks + 1G-SFP + RJ45 pairs); IM = timing module
                  (GNSS/10MHz/1PPS); 2 PSU bays + vent left; viewBox 3422.5x312.5.
asr920-24sz     : 24SZ-M. Fan+PSU left section; 24x GE SFP single row (ports 0-23);
                  4x 10G SFP+ in 2x2 grid (uplinks 24-27); PSU right; 3422.5x315.
"""
from __future__ import annotations

import json
import shutil
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


# --------------------------------------------------------------------------- #
# ASR920-12SZ-IM-CC : modular timing chassis, viewBox 3422.5x312.5             #
#   Ports run descending 15->0 left-to-right:                                  #
#     10G SFP+ uplinks 12-15 and 1G-SFP 8-11 in a single row inside the cage;  #
#     RJ45 0-7 as four vertical pairs near the branding;                       #
#   IM 0/1 = the timing module (GNSS / 10MHz / 1PPS); 2 PSU bays + vent left.  #
# --------------------------------------------------------------------------- #
_IM_W, _IM_H = 1.3, 36.0          # SFP / uplink single-row box
_IM_RY = 24.0                     # single-row centre (inside the dark cage)
_IM_RT, _IM_RB = 15.0, 32.0       # RJ45 pair rows
_IM_RW, _IM_RH = 1.5, 15.0
LAYOUTS["asr920-12sz-im"] = {
    # 10G SFP+ uplinks 12-15 (labels 15+ 14+ 13+ 12+)
    "hotspot-uplink-15": (42.0, _IM_RY, _IM_W, _IM_H),
    "hotspot-uplink-14": (45.2, _IM_RY, _IM_W, _IM_H),
    "hotspot-uplink-13": (48.8, _IM_RY, _IM_W, _IM_H),
    "hotspot-uplink-12": (52.2, _IM_RY, _IM_W, _IM_H),
    # 1G SFP-GE 8-11 (labels 11 10 9 8)
    "hotspot-sfp-11": (55.8, _IM_RY, _IM_W, _IM_H),
    "hotspot-sfp-10": (59.2, _IM_RY, _IM_W, _IM_H),
    "hotspot-sfp-9": (62.6, _IM_RY, _IM_W, _IM_H),
    "hotspot-sfp-8": (66.0, _IM_RY, _IM_W, _IM_H),
    # RJ45 0-7 : four vertical pairs (labels 7/6 5/4 3/2 1/0), even=bottom
    "hotspot-rj45-7": (74.0, _IM_RT, _IM_RW, _IM_RH),
    "hotspot-rj45-6": (74.0, _IM_RB, _IM_RW, _IM_RH),
    "hotspot-rj45-5": (77.3, _IM_RT, _IM_RW, _IM_RH),
    "hotspot-rj45-4": (77.3, _IM_RB, _IM_RW, _IM_RH),
    "hotspot-rj45-3": (80.4, _IM_RT, _IM_RW, _IM_RH),
    "hotspot-rj45-2": (80.4, _IM_RB, _IM_RW, _IM_RH),
    "hotspot-rj45-1": (83.2, _IM_RT, _IM_RW, _IM_RH),
    "hotspot-rj45-0": (83.2, _IM_RB, _IM_RW, _IM_RH),
    # IM 0/1 = timing module (GNSS / 10MHz / 1PPS)
    "hotspot-im-0": (38.0, 30.0, 9.0, 52.0),
    # PSU bays + vent (left)
    "hotspot-psu-0": (10.5, 35.0, 11.0, 56.0),
    "hotspot-psu-1": (22.0, 35.0, 11.0, 56.0),
    "hotspot-fan-0": (31.0, 35.0, 6.0, 56.0),
}


# --------------------------------------------------------------------------- #
# ASR920-24SZ-M : 24x GE SFP (single row) + 4x 10G uplinks (2x2 grid)       #
#   viewBox 3422.5 x 315.06 — same chassis width as 12CZ                     #
#   Port x-centres derived from y=57 SFP-cage box elements at 36px pitch     #
#   (boxes 1343-2168 for GigE 0-23; 2x2 uplink grid at x≈78.3 / 81.2%)      #
#   PSU panels extracted from SVG fill paths: x=1164.5 w=123 and x=2880.5   #
# --------------------------------------------------------------------------- #
_GW, _GH = 1.05, 70.0          # GigE SFP hotspot
_GY = 47.0                     # single row y-centre
# GigE port x-centres (% of 3422.5): boxes[i]+10.5 / 3422.5 * 100
_GE_X = [
    39.55, 40.60, 41.66, 42.71, 43.76, 44.81,  # 0-5
    45.87, 46.92, 47.93, 48.98, 50.04, 51.09,  # 6-11
    52.14, 53.19, 54.25, 55.30, 56.35, 57.35,  # 12-17
    58.40, 59.45, 60.51, 61.56, 62.61, 63.67,  # 18-23
]
_UW24, _UH24 = 2.0, 20.0
_UTOP, _UBOT = 33.0, 55.0
# Two uplink columns centred on LED-arrow indicators at x≈78.31% and 81.16%
_UCOL = [78.31, 81.16]
LAYOUTS["asr920-24sz"] = {
    **{f"hotspot-sfp-{i}": (_GE_X[i], _GY, _GW, _GH) for i in range(24)},
    # TenGigE uplinks 24-27: 2 columns × 2 rows (even=top, odd=bottom)
    "hotspot-uplink-24": (_UCOL[0], _UTOP, _UW24, _UH24),
    "hotspot-uplink-25": (_UCOL[0], _UBOT, _UW24, _UH24),
    "hotspot-uplink-26": (_UCOL[1], _UTOP, _UW24, _UH24),
    "hotspot-uplink-27": (_UCOL[1], _UBOT, _UW24, _UH24),
    # PSU bays: panel bounds from SVG fill paths
    "hotspot-psu-0": (35.82, 47.86, 3.59, 67.13),
    "hotspot-psu-1": (86.29, 47.86, 4.25, 67.13),
    # Fan tray bay (left section, before PSU 0)
    "hotspot-fan-0": (25.0, 47.86, 10.0, 67.13),
}

# ---------------------------------------------------------------------------
# EPNM artwork overrides — profiles whose build-script placeholder SVG must be
# replaced with the real EPNM front artwork. apply() copies the source SVG to
# epnm-front.svg and updates width/height in normalized.json accordingly.
# ---------------------------------------------------------------------------
_EPNM: dict[str, tuple[str, float, float]] = {
    # profile: (path relative to repo root, svg_w, svg_h)
    "asr920-24sz": (
        "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
        "NCS42XXFamily/Cisco_ASR_920_24SZM_Router/images/ASR-920-24SZ-M-Front.svg",
        3422.5, 315.06,
    ),
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
    epnm = _EPNM.get(profile)
    for base in ("frontend/public/chassis-assets", "backend/app/data/chassis"):
        path = repo / base / profile / "normalized.json"
        data = json.loads(path.read_text())
        view = data["views"][0]
        if epnm:
            src_rel, epnm_w, epnm_h = epnm
            src = repo / src_rel
            dst = path.parent / "epnm-front.svg"
            shutil.copy2(src, dst)
            img = f"/chassis-assets/{profile}/epnm-front.svg"
            view["image"] = img
            view["sourceImage"] = img
            view["width"] = epnm_w
            view["height"] = epnm_h
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
