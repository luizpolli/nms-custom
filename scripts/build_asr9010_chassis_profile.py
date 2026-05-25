#!/usr/bin/env python3
"""Build the static ASR 9010 chassis-view profile from the EPNM figures package.

This wraps ``scripts/normalize_chassis_assets.py`` so the work is reproducible:

- Reads ``.local/chassis-assets/figures.tar.gz`` (kept out of git).
- Normalizes the IOSXR ASR 9010 profile + inventory + SVG.
- Sanitizes the front SVG (no inline scripts / external refs).
- Writes the normalized JSON + curated SVG + per-slot pluggable SVGs to both
  the backend and frontend asset folders.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TARBALL = REPO_ROOT / ".local" / "chassis-assets" / "figures.tar.gz"
BACKEND_DIR = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "asr9010"
FRONTEND_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "asr9010"
SVG_NAME = "ASR-9010-AC-Front.svg"

sys.path.insert(0, str(SCRIPTS_DIR))

import normalize_chassis_assets as ncha  # noqa: E402  (path injection above)


_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_EXT_HREF_RE = re.compile(r"\s+xlink:href=\"https?:[^\"]+\"", re.IGNORECASE)
_EXT_PLAIN_HREF_RE = re.compile(r"\s+href=\"https?:[^\"]+\"", re.IGNORECASE)


def sanitize_svg(text: str) -> str:
    cleaned = _SCRIPT_RE.sub("", text)
    cleaned = _EXT_HREF_RE.sub("", cleaned)
    cleaned = _EXT_PLAIN_HREF_RE.sub("", cleaned)
    return cleaned


def extract_chassis_svg() -> str:
    with tarfile.open(TARBALL, "r:gz") as archive:
        text = ncha.read_text(archive, ncha.ASR9010_PATHS["image"])
    return sanitize_svg(text)


def extract_asset_svgs(asset_type_ids: list[str]) -> dict[str, str]:
    assets: dict[str, str] = {}
    with tarfile.open(TARBALL, "r:gz") as archive:
        for type_id in asset_type_ids:
            source = f"{ncha.ASR9010_PLUGGABLE_IMAGE_PREFIX}/{type_id}.svg"
            try:
                svg = ncha.read_text(archive, source)
            except FileNotFoundError:
                print(f"warning=missing_asset typeId={type_id} source={source}")
                continue
            assets[type_id] = sanitize_svg(svg)
    return assets


def write_outputs(normalized: dict[str, Any], chassis_svg: str, asset_svgs: dict[str, str]) -> None:
    payload = json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    for out_dir in (BACKEND_DIR, FRONTEND_DIR):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / SVG_NAME).write_text(chassis_svg, encoding="utf-8")
        (out_dir / "normalized.json").write_text(payload, encoding="utf-8")
        for type_id, svg in asset_svgs.items():
            (out_dir / f"{type_id}.svg").write_text(svg, encoding="utf-8")


def main() -> None:
    if not TARBALL.exists():
        raise SystemExit(f"Missing chassis-assets tarball at {TARBALL}")

    normalized = ncha.normalize_asr9010(TARBALL)
    chassis_svg = extract_chassis_svg()
    asset_svgs = extract_asset_svgs(ncha.asset_type_ids(normalized))
    write_outputs(normalized, chassis_svg, asset_svgs)

    hotspots = normalized["views"][0]["hotspots"]
    mapped = sum(1 for h in hotspots if h["inventoryId"])
    print(f"profile={normalized['profileId']}")
    print(f"components={len(normalized['componentsById'])}")
    print(f"hotspots={len(hotspots)}")
    print(f"mapped_hotspots={mapped}")
    print(f"assets={len(asset_svgs)}")
    print(f"backend={BACKEND_DIR}")
    print(f"frontend={FRONTEND_DIR}")


if __name__ == "__main__":
    main()
