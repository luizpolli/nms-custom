#!/usr/bin/env python3
"""Extract per-module port cage geometry from the EPNM pluggables.json.

The EPNM file (docs/.../ASR9K-IOSXR/pluggables/data/pluggables.json) carries,
for every module/line-card PID, the exact port cage rectangles in both
horizontal and vertical orientations (SVG viewBox coordinate space). This is the
ground truth for placing port hotspots on the real faceplate art.

The file also contains transform-rule strings with embedded regex (invalid JSON
escapes), so we don't full-parse it; instead we isolate each requested module's
brace-balanced block and regex out its slot list.

Usage: python3 scripts/extract_pluggables_ports.py [PID ...]
Outputs a compact JSON map to stdout: { PID: {svgImageId, orientation, ports:[{id,nodeId,vertical,horizontal}]} }
"""
import json
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / (
    "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
    "ASR9K-IOSXR/pluggables/data/pluggables.json"
)

RECT_RE = re.compile(
    r'"(horizontal|vertical)"\s*:\s*\{\s*"x"\s*:\s*([\d.]+)\s*,\s*"y"\s*:\s*([\d.]+)\s*,'
    r'\s*"width"\s*:\s*([\d.]+)\s*,\s*"height"\s*:\s*([\d.]+)\s*\}'
)
SLOT_ID_RE = re.compile(r'"id"\s*:\s*"([^"]+)"\s*,\s*"nodeId"\s*:\s*"([^"]+)"')


def module_block(text: str, pid: str) -> str | None:
    """Return the brace-balanced object body for a top-level `"PID": { ... }`."""
    needle = f'"{pid}": {{'
    start = text.find(needle)
    if start < 0:
        return None
    i = start + len(needle) - 1  # at the opening brace
    depth = 0
    for j in range(i, len(text)):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i : j + 1]
    return None


def parse_module(text: str, pid: str) -> dict | None:
    block = module_block(text, pid)
    if not block:
        return None
    svg = re.search(r'svgImageId\s*:\s*"([^"]+)"', block)
    orient = {}
    om = re.search(r'orientation\s*:\s*\{(.*?)\}\s*,', block, re.S)
    if om:
        for name in ("horizontal", "vertical"):
            mm = re.search(rf'{name}\s*:\s*\{{\s*width\s*:\s*([\d.]+)\s*,\s*height\s*:\s*([\d.]+)', om.group(1))
            if mm:
                orient[name] = {"width": float(mm.group(1)), "height": float(mm.group(2))}
    # iterate slots: each id/nodeId is followed by an origin with two rects.
    # Bound each slot's search window at the next slot id so rects never bleed
    # across slot boundaries.
    matches = list(SLOT_ID_RE.finditer(block))
    ports = []
    for idx, sm in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        tail = block[sm.end() : end]
        rects = {}
        for m in RECT_RE.finditer(tail):
            rects.setdefault(m.group(1), {"x": float(m.group(2)), "y": float(m.group(3)),
                                          "w": float(m.group(4)), "h": float(m.group(5))})
        if not rects:
            continue
        ports.append({"id": sm.group(1), "nodeId": sm.group(2),
                      "vertical": rects.get("vertical"), "horizontal": rects.get("horizontal")})
    return {"svgImageId": svg.group(1) if svg else None, "orientation": orient, "ports": ports}


def main() -> None:
    text = SRC.read_text()
    pids = sys.argv[1:] or ["A9K-4T-B", "A9K-8T-L", "A9K-2T20GE-L", "A9K-MOD80-TR"]
    out = {}
    for pid in pids:
        mod = parse_module(text, pid)
        if mod:
            out[pid] = mod
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
