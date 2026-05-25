#!/usr/bin/env python3
"""Audit EPNM chassis-view asset packages without extracting them."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import tarfile
from pathlib import Path


DEVICE_PROFILE_RE = re.compile(
    r"chassisview/com\.cisco\.prime\.deviceprofile/"
    r"(?P<family>[^/]+)/(?P<profile>[^/]+)/(?P<section>data|images)/(?P<file>[^/]+)$"
)
PIDSUPPORT_INVENTORY_RE = re.compile(
    r"chassisview/v2/pidsupport/inventory/"
    r"(?P<family>[^/]+)/(?P<profile>[^/]+)/(?P<file>[^/]+\.json)$"
)
V2_DATA_RE = re.compile(r"chassisview/v2/data/(?P<file>[^/]+\.json)$")
IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".gif"}


def classify_image(name: str) -> str:
    lowered = name.lower()
    if "front" in lowered or "_core" in lowered and "rear" not in lowered:
        return "front"
    if "rear" in lowered:
        return "rear"
    if "filler" in lowered:
        return "filler"
    if "fan" in lowered:
        return "fan"
    if "power" in lowered or "psu" in lowered or "pwr" in lowered:
        return "power"
    if "port" in lowered:
        return "ports"
    return "other"


def audit(tar_path: Path) -> dict:
    profiles: dict[str, dict] = {}
    pidsupport_inventory: dict[str, dict] = {}
    v2_data: list[str] = []
    totals = collections.Counter()

    with tarfile.open(tar_path, "r:gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            totals["files"] += 1
            path = member.name
            suffix = Path(path).suffix.lower()
            if suffix in IMAGE_SUFFIXES:
                totals["images"] += 1
            if suffix == ".json":
                totals["json"] += 1

            match = DEVICE_PROFILE_RE.search(path)
            if match:
                family = match.group("family")
                profile = match.group("profile")
                section = match.group("section")
                filename = match.group("file")
                key = f"{family}/{profile}"
                item = profiles.setdefault(
                    key,
                    {
                        "family": family,
                        "profile": profile,
                        "data_files": [],
                        "images": collections.Counter(),
                        "sample_images": [],
                    },
                )
                if section == "data":
                    item["data_files"].append(path)
                elif suffix in IMAGE_SUFFIXES:
                    item["images"][classify_image(filename)] += 1
                    if len(item["sample_images"]) < 5:
                        item["sample_images"].append(path)
                continue

            match = PIDSUPPORT_INVENTORY_RE.search(path)
            if match:
                family = match.group("family")
                profile = match.group("profile")
                key = f"{family}/{profile}"
                item = pidsupport_inventory.setdefault(key, {"family": family, "profile": profile, "files": []})
                item["files"].append(path)
                continue

            match = V2_DATA_RE.search(path)
            if match:
                v2_data.append(path)

    for item in profiles.values():
        item["images"] = dict(item["images"])
        item["data_files"].sort()
    for item in pidsupport_inventory.values():
        item["files"].sort()

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tar_path": str(tar_path),
        "totals": dict(totals),
        "device_profiles": dict(sorted(profiles.items())),
        "pidsupport_inventory": dict(sorted(pidsupport_inventory.items())),
        "v2_data": sorted(v2_data),
    }


def write_markdown(report: dict, output_path: Path) -> None:
    profiles = report["device_profiles"]
    inventory = report["pidsupport_inventory"]
    lines = [
        "# Chassis Asset Audit",
        "",
        f"Generated from `{report['tar_path']}`.",
        "",
        "## Totals",
        "",
        f"- Files: {report['totals'].get('files', 0)}",
        f"- Images: {report['totals'].get('images', 0)}",
        f"- JSON files: {report['totals'].get('json', 0)}",
        f"- Device profiles: {len(profiles)}",
        f"- Inventory samples: {len(inventory)}",
        "",
        "## Recommended v1.1 Starting Profiles",
        "",
    ]

    for key in [
        "asr901Family/Cisco_ASR_903_Router",
        "ASR9K-64CE/Cisco_ASR_9906_Router",
        "ASR9K-64CE/Cisco_ASR_9006_Router",
    ]:
        profile = profiles.get(key)
        inv = inventory.get(key) or inventory.get(key.replace("asr901Family", "asr90xFamily"))
        if not profile and not inv:
            continue
        lines.append(f"### {key}")
        if profile:
            lines.append(f"- Data files: {len(profile['data_files'])}")
            lines.append(f"- Images by type: `{json.dumps(profile['images'], sort_keys=True)}`")
            if profile["sample_images"]:
                lines.append("- Sample images:")
                lines.extend(f"  - `{path}`" for path in profile["sample_images"])
        if inv:
            lines.append(f"- Inventory/chassis samples: {len(inv['files'])}")
            lines.extend(f"  - `{path}`" for path in inv["files"])
        lines.append("")

    lines.extend(
        [
            "## Top Families",
            "",
        ]
    )
    family_counts = collections.Counter(profile["family"] for profile in profiles.values())
    for family, count in family_counts.most_common():
        lines.append(f"- `{family}`: {count} profiles")

    lines.extend(["", "## v2 Data Files", ""])
    lines.extend(f"- `{path}`" for path in report["v2_data"])
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an EPNM chassis-view figures tarball.")
    parser.add_argument("tarball", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = audit(args.tarball)

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(report, args.markdown_output)

    print(json.dumps(report["totals"], indent=2, sort_keys=True))
    print(f"device_profiles={len(report['device_profiles'])}")
    print(f"inventory_samples={len(report['pidsupport_inventory'])}")


if __name__ == "__main__":
    main()
