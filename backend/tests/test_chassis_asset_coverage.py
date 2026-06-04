"""Guardrail: ensure chassis hotspot asset coverage doesn't silently regress.

Background: commit ``fc9dad3`` stripped every ``asset`` block from every
chassis ``normalized.json`` in a panic fix and was only caught by visual
inspection.  This test makes the same mistake impossible to land without
explicitly bumping the floor below.

The floor is intentionally a bit below the current 93.1% so that legitimate
schema changes (e.g. adding a new profile with no per-PID images) don't
break CI, but a blanket strip will always be caught.
"""
from __future__ import annotations

import json
from pathlib import Path

CHASSIS_DIR = (
    Path(__file__).resolve().parent.parent / "app" / "data" / "chassis"
)

# Coverage floor in percent.  Current coverage is ~93.1%; we set the floor
# to 85% to allow small legitimate fluctuations while still catching any
# bulk strip event.  Bump intentionally if a new stub profile is added.
ASSET_COVERAGE_FLOOR_PCT = 85.0

# Profiles intentionally excluded from the coverage calculation (e.g. ASR5k
# which is documented as not supported).  Empty for now.
EXCLUDED_PROFILES: set[str] = set()


def _iter_hotspots():
    for profile_dir in sorted(CHASSIS_DIR.iterdir()):
        if not profile_dir.is_dir():
            continue
        if profile_dir.name in EXCLUDED_PROFILES:
            continue
        normalized = profile_dir / "normalized.json"
        if not normalized.exists():
            continue
        data = json.loads(normalized.read_text())
        for view in data.get("views", []):
            for hotspot in view.get("hotspots", []):
                yield profile_dir.name, hotspot


def test_global_asset_coverage_above_floor() -> None:
    total = 0
    with_asset = 0
    for _profile, hotspot in _iter_hotspots():
        total += 1
        if hotspot.get("asset"):
            with_asset += 1
    assert total > 0, "no chassis hotspots found — data directory missing?"
    pct = 100.0 * with_asset / total
    assert pct >= ASSET_COVERAGE_FLOOR_PCT, (
        f"chassis hotspot asset coverage regressed: {with_asset}/{total} "
        f"= {pct:.1f}% < floor {ASSET_COVERAGE_FLOOR_PCT}%.  "
        "If this is intentional, bump ASSET_COVERAGE_FLOOR_PCT in this file "
        "with a justification in the commit message; do NOT silently strip "
        "asset blocks to fix render bugs — use "
        "frontend/src/pages/inventory/chassis/overlayPolicy.ts instead.  "
        "See docs/chassis-view-overlay-policy.md."
    )


def test_asset_blocks_preserve_required_metadata() -> None:
    """Every asset block must carry image + typeId (used by inspector/alarms)."""
    missing: list[str] = []
    for profile, hotspot in _iter_hotspots():
        asset = hotspot.get("asset")
        if not asset:
            continue
        if not asset.get("image") or not asset.get("typeId"):
            missing.append(f"{profile}:{hotspot.get('id', '?')}")
    assert not missing, (
        "asset blocks missing image or typeId (these are required by the "
        f"inspector panel and alarm correlation): {missing[:10]}"
        + (f" ... +{len(missing) - 10} more" if len(missing) > 10 else "")
    )
