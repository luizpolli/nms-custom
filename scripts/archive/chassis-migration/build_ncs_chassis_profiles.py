#!/usr/bin/env python3
"""Build Cisco NCS chassis-view profiles from normalized ENTITY-MIB data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "docs" / "snmpwalks" / "normalized"
FRONTEND_ROOT = REPO_ROOT / "frontend" / "public" / "chassis-assets"
BACKEND_ROOT = REPO_ROOT / "backend" / "app" / "data" / "chassis"


@dataclass(frozen=True)
class FrontItem:
    physical_index: int
    label: str
    x: float
    y: float
    w: float
    h: float
    kind: str = "module"


@dataclass(frozen=True)
class ProfileSpec:
    key: str
    profile_id: str
    platform: str
    svg_name: str
    width: int
    height: int
    title: str
    subtitle: str
    items: tuple[FrontItem, ...]


def _ncs560_items() -> tuple[FrontItem, ...]:
    items: list[FrontItem] = [
        FrontItem(1, "RP0", 42, 72, 130, 104, "rp"),
        FrontItem(784, "MGMT0", 58, 194, 92, 28, "port"),
        FrontItem(4097, "RP1", 42, 244, 130, 104, "rp"),
        FrontItem(4880, "MGMT1", 58, 366, 92, 28, "port"),
        FrontItem(16385, "0/2", 210, 70, 174, 46, "linecard"),
        FrontItem(24577, "0/4", 210, 152, 386, 46, "linecard"),
        FrontItem(28673, "0/5", 210, 234, 386, 46, "linecard"),
    ]

    for port in range(8):
        items.append(FrontItem(17184 + port, f"0/2/{port}", 410 + port * 58, 72, 48, 34, "bay"))
    for port in range(17):
        items.append(FrontItem(25376 + port, f"0/4/{port}", 620 + (port % 9) * 58, 136 + (port // 9) * 44, 48, 34, "bay"))
    for port in range(17):
        items.append(FrontItem(29472 + port, f"0/5/{port}", 620 + (port % 9) * 58, 218 + (port // 9) * 44, 48, 34, "bay"))

    items.extend(
        [
            FrontItem(73729, "FT0", 994, 72, 152, 58, "fan"),
            FrontItem(77825, "FT1", 994, 166, 152, 58, "fan"),
            FrontItem(81921, "FT2", 994, 260, 152, 58, "fan"),
            FrontItem(86017, "PM0", 408, 334, 160, 54, "power"),
            FrontItem(90113, "PM1", 608, 334, 160, 54, "power"),
            FrontItem(8384513, "Chassis", 28, 42, 1140, 368, "chassis"),
        ]
    )
    return tuple(items)


def _ncs540_items() -> tuple[FrontItem, ...]:
    items: list[FrontItem] = [FrontItem(1, "RP0/CPU0", 52, 90, 156, 134, "rp")]
    for port in range(28):
        items.append(FrontItem(801 + port, str(port), 260 + (port % 14) * 58, 108 + (port // 14) * 66, 48, 36, "bay"))
    items.extend(
        [
            FrontItem(4097, "FT0", 962, 86, 164, 64, "fan"),
            FrontItem(8982, "PM0", 280, 280, 154, 58, "power"),
            FrontItem(13078, "PM1", 468, 280, 154, 58, "power"),
            FrontItem(8384513, "Chassis", 28, 42, 1128, 336, "chassis"),
        ]
    )
    return tuple(items)


SPECS = (
    ProfileSpec(
        key="ncs55a1",
        profile_id="Cisco_NCS55A1",
        platform="Cisco NCS55A1",
        svg_name="NCS55A1-Front.svg",
        width=1280,
        height=430,
        title="Cisco NCS55A1",
        subtitle="Fixed 36x100G Scale Route Processor",
        items=(),
    ),
    ProfileSpec(
        key="ncs560",
        profile_id="Cisco_NCS560",
        platform="Cisco NCS560",
        svg_name="NCS560-Front.svg",
        width=1280,
        height=460,
        title="Cisco NCS560",
        subtitle="Modular access router from ENTITY-MIB inventory",
        items=_ncs560_items(),
    ),
    ProfileSpec(
        key="ncs540",
        profile_id="Cisco_NCS540",
        platform="Cisco NCS540",
        svg_name="NCS540-Front.svg",
        width=1240,
        height=420,
        title="Cisco NCS540",
        subtitle="Fixed access router from ENTITY-MIB inventory",
        items=_ncs540_items(),
    ),
)


def port_number(name: str) -> int | None:
    match = re.search(r"(?:HundredGigE|TwentyFiveGigE|TenGigE|GigabitEthernet|SFP|QSFP).*/(\d+)(?:/\d+)?$", name)
    return int(match.group(1)) if match else None


def clean_port_name(name: str) -> str:
    for prefix in ("0/RP0-", "0/RP0/CPU0-", "0/RP1-", "0/2-", "0/4-", "0/5-"):
        name = name.removeprefix(prefix)
    return name


def add_port_links(components: dict[str, dict[str, Any]]) -> None:
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    for component in components.values():
        parent = component.get("containedPhysicalIndex")
        if isinstance(parent, int):
            children_by_parent.setdefault(parent, []).append(component)

    for component in components.values():
        name = str(component.get("name", ""))
        if component.get("physicalClassLabel") != "port" or port_number(name) is None:
            continue
        component["ports"] = [
            {
                "id": str(component["physicalIndex"]),
                "name": clean_port_name(name),
                "portId": component["physicalIndex"],
            }
        ]

    for bay in components.values():
        name = str(bay.get("name", ""))
        if bay.get("physicalClassLabel") != "container" or not re.search(r"(?:QSFP|SFP)\d* bay", name):
            continue
        parent_index = bay.get("containedPhysicalIndex")
        if not isinstance(parent_index, int):
            continue
        sibling_ports = [
            child
            for child in children_by_parent.get(parent_index, [])
            if child.get("physicalClassLabel") == "port" and child.get("ports")
        ]
        bay["ports"] = [
            {"id": str(port["physicalIndex"]), "name": clean_port_name(str(port["name"])), "portId": port["physicalIndex"]}
            for port in sorted(sibling_ports, key=lambda item: int(item["physicalIndex"]))
        ]


def find_component(components: dict[str, dict[str, Any]], physical_index: int) -> dict[str, Any]:
    return components[f"component-{physical_index}"]


def hotspot(component: dict[str, Any], item: FrontItem) -> dict[str, Any]:
    return {
        "id": f"hotspot-{item.kind}-{item.physical_index}",
        "slotKey": str(component.get("slotKey") or component.get("name") or item.label),
        "label": item.label,
        "inventoryId": component["id"],
        "physicalIndex": component["physicalIndex"],
        "empty": item.kind == "bay" and len(component.get("childIds", [])) == 0,
        "bounds": {"x": item.x, "y": item.y, "w": item.w, "h": item.h},
        "metadata": {
            "sourceName": component.get("name"),
            "sourceTypeId": component.get("typeId"),
            "modelName": component.get("modelName"),
            "modelTypeId": component.get("typeId"),
        },
    }


def rect(item: FrontItem, component: dict[str, Any]) -> str:
    colors = {
        "bay": ("#1d4ed8" if component.get("childIds") else "#1f2937", "#93c5fd" if component.get("childIds") else "#4b5563"),
        "rp": ("#374151", "#94a3b8"),
        "linecard": ("#334155", "#64748b"),
        "fan": ("#3f3f46", "#a1a1aa"),
        "power": ("#475569", "#94a3b8"),
        "port": ("#111827", "#60a5fa"),
    }
    fill, stroke = colors.get(item.kind, ("none", "none"))
    if item.kind == "chassis":
        return ""
    label_y = item.y + item.h + (16 if item.kind == "bay" else -item.h / 2 + 5)
    return (
        f'<rect x="{item.x}" y="{item.y}" width="{item.w}" height="{item.h}" rx="5" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"/>'
        f'<text x="{item.x + item.w / 2}" y="{label_y}" text-anchor="middle" font-size="12" '
        f'font-family="Arial, Helvetica, sans-serif" fill="#f8fafc">{item.label}</text>'
    )


def build_svg(spec: ProfileSpec, components: dict[str, dict[str, Any]]) -> str:
    front = "\n  ".join(rect(item, find_component(components, item.physical_index)) for item in spec.items)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {spec.width} {spec.height}" width="{spec.width}" height="{spec.height}" role="img" aria-label="{spec.title} front view">
  <defs>
    <linearGradient id="face" x1="0" x2="1">
      <stop offset="0" stop-color="#111827"/>
      <stop offset=".55" stop-color="#1f2937"/>
      <stop offset="1" stop-color="#0f172a"/>
    </linearGradient>
    <linearGradient id="metal" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#e5e7eb"/>
      <stop offset="1" stop-color="#9ca3af"/>
    </linearGradient>
  </defs>
  <rect x="28" y="42" width="{spec.width - 112}" height="{spec.height - 82}" rx="10" fill="url(#metal)" stroke="#6b7280" stroke-width="3"/>
  <rect x="46" y="64" width="{spec.width - 148}" height="{spec.height - 126}" rx="7" fill="url(#face)" stroke="#030712" stroke-width="2"/>
  <text x="70" y="88" font-size="20" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="#f9fafb">{spec.title}</text>
  <text x="70" y="112" font-size="13" font-family="Arial, Helvetica, sans-serif" fill="#9ca3af">{spec.subtitle}</text>
  {front}
</svg>
'''


def build_profile(spec: ProfileSpec) -> None:
    if spec.key == "ncs55a1":
        # The original NCS55A1 builder has a more specific faceplate layout.
        return
    source_path = SOURCE_DIR / f"{spec.key}-entity-mib.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    components = source["componentsById"]
    add_port_links(components)
    hotspots = [hotspot(find_component(components, item.physical_index), item) for item in spec.items]

    profile = {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "deviceId": f"example-{spec.key}",
        "profileId": spec.profile_id,
        "platform": spec.platform,
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": f"/chassis-assets/{spec.key}/{spec.svg_name}",
                "width": spec.width,
                "height": spec.height,
                "sourceWidth": spec.width,
                "sourceHeight": spec.height,
                "hotspots": hotspots,
            }
        ],
        "tree": source["tree"],
        "componentsById": components,
        "physicalIndexToComponentId": source["physicalIndexToComponentId"],
        "source": {
            "type": "entity-mib-derived-static-profile",
            "profile": str(source_path.relative_to(REPO_ROOT)),
        },
    }

    for out_dir in (FRONTEND_ROOT / spec.key, BACKEND_ROOT / spec.key):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / spec.svg_name).write_text(build_svg(spec, components), encoding="utf-8")
        (out_dir / "normalized.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {out_dir / 'normalized.json'}")


def main() -> None:
    for spec in SPECS:
        build_profile(spec)


if __name__ == "__main__":
    main()
