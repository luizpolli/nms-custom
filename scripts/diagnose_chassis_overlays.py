#!/usr/bin/env python3
"""
Diagnose chassis-view overlay redundancy.

For each chassis profile, measure how many SVG path bounding boxes from the
base chassis SVG overlap each hotspot's bounds.  A high overlap count means
the base SVG already paints the component at that hotspot -> our hotspot
asset overlay is redundant and will visually double up.

Output: a per-profile table classifying each hotspot type as:
  EMPTY     paths_in_region <= 2   -> overlay needed (base SVG is frame-only)
  SPARSE    3..15                  -> overlay probably needed, decorative paths
  DENSE     16..50                 -> ambiguous, review case by case
  PAINTED   > 50                   -> overlay redundant, base SVG paints it
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "backend" / "app" / "data" / "chassis"
ASSETS_DIR = ROOT / "frontend" / "public" / "chassis-assets"

NUM_RE = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def path_bboxes(svg: str) -> list[tuple[float, float, float, float]]:
    """Coarse bbox per <path d="..."/> using raw coordinate min/max.

    Not exact (ignores SVG commands, control points overshoot) but good
    enough to count "does this path live inside this rectangle".
    """
    boxes = []
    for m in re.finditer(r'd="([^"]+)"', svg):
        d = m.group(1)
        nums = NUM_RE.findall(d)
        if len(nums) < 4:
            continue
        try:
            xs = [float(nums[i]) for i in range(0, len(nums) - 1, 2)]
            ys = [float(nums[i]) for i in range(1, len(nums), 2)]
            if xs and ys:
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
        except ValueError:
            continue
    # also include <rect ...>
    for m in re.finditer(
        r'<rect[^>]*?\bx="([\d.\-]+)"[^>]*?\by="([\d.\-]+)"'
        r'[^>]*?\bwidth="([\d.\-]+)"[^>]*?\bheight="([\d.\-]+)"',
        svg,
    ):
        try:
            x, y, w, h = map(float, m.groups())
            boxes.append((x, y, x + w, y + h))
        except ValueError:
            continue
    return boxes


def classify(count: int) -> str:
    # Tuned for *contained* path count (paths mostly inside the hotspot region).
    if count <= 1:
        return "EMPTY  "
    if count <= 5:
        return "SPARSE "
    if count <= 15:
        return "DENSE  "
    return "PAINTED"


def hotspot_type(hid: str) -> str:
    # hotspot-sfp-3 -> sfp, hotspot-bay-801 -> bay, etc.
    parts = hid.split("-")
    if len(parts) >= 2 and parts[0] == "hotspot":
        return parts[1]
    return hid


def find_base_svg(profile_dir: Path) -> Path | None:
    for f in profile_dir.glob("*.svg"):
        # skip modules/
        return f
    return None


def analyze_profile(profile: str) -> dict:
    profile_data = DATA_DIR / profile / "normalized.json"
    if not profile_data.exists():
        return {"profile": profile, "skipped": "no normalized.json"}
    data = json.loads(profile_data.read_text())

    assets_dir = ASSETS_DIR / profile
    base_svg_path = find_base_svg(assets_dir)
    if not base_svg_path:
        return {"profile": profile, "skipped": "no base svg"}
    svg = base_svg_path.read_text()
    boxes = path_bboxes(svg)

    per_type: dict[str, list[int]] = defaultdict(list)
    redundant_hotspots: list[tuple[str, int, str]] = []

    for view in data.get("views", []):
        for h in view.get("hotspots", []):
            if not h.get("asset"):
                continue
            b = h.get("bounds")
            if not b:
                continue
            x0, y0 = b["x"], b["y"]
            x1, y1 = x0 + b["w"], y0 + b["h"]
            region_area = max(1.0, (x1 - x0) * (y1 - y0))
            # Count only paths that are MOSTLY contained in the region.
            # A path "belongs" to the region if >=70% of its bbox area sits
            # inside the hotspot bounds.  This filters big chassis-frame
            # paths that span the whole image and would otherwise
            # falsely match every hotspot.
            contained = 0
            for (px0, py0, px1, py1) in boxes:
                pw = max(0.0, px1 - px0)
                ph = max(0.0, py1 - py0)
                parea = pw * ph
                if parea <= 0:
                    continue
                ix0 = max(px0, x0); iy0 = max(py0, y0)
                ix1 = min(px1, x1); iy1 = min(py1, y1)
                if ix1 <= ix0 or iy1 <= iy0:
                    continue
                inter = (ix1 - ix0) * (iy1 - iy0)
                # Skip paths that are much larger than the region (chassis frame).
                if parea > 4 * region_area:
                    continue
                if inter / parea >= 0.7:
                    contained += 1
            t = hotspot_type(h["id"])
            per_type[t].append(contained)
            if contained > 15:
                redundant_hotspots.append((h["id"], contained, h["asset"].get("typeId", "?")))

    summary = {}
    for t, counts in per_type.items():
        avg = sum(counts) / len(counts) if counts else 0
        summary[t] = {
            "n": len(counts),
            "avg_overlap": round(avg, 1),
            "verdict": classify(int(avg)),
        }

    return {
        "profile": profile,
        "svg_paths": len(boxes),
        "by_type": summary,
        "redundant_count": len(redundant_hotspots),
    }


def main() -> int:
    profiles = sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir())
    print(f"{'PROFILE':22s} {'PATHS':>6s}  HOTSPOT TYPES (n, avg-paths-in-region, verdict)")
    print("-" * 100)

    redundant_total = 0
    for prof in profiles:
        r = analyze_profile(prof)
        if "skipped" in r:
            print(f"{prof:22s}  --     [skipped: {r['skipped']}]")
            continue
        types_str = "  ".join(
            f"{t}:{v['n']}x{v['avg_overlap']:.0f}={v['verdict'].strip()}"
            for t, v in sorted(r["by_type"].items())
        )
        print(f"{prof:22s} {r['svg_paths']:>6d}  {types_str}")
        redundant_total += r["redundant_count"]

    print("-" * 100)
    print(f"Total hotspots flagged as PAINTED (>15 base paths mostly contained in region): {redundant_total}")
    print()
    print("Verdict legend:")
    print("  EMPTY   (<=1 contained paths)  base SVG is frame-only -> overlay NEEDED")
    print("  SPARSE  (2..5)                 decorative paths       -> overlay needed")
    print("  DENSE   (6..15)                ambiguous              -> manual review")
    print("  PAINTED (>15)                  base SVG already draws -> overlay REDUNDANT (causes doubling)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
