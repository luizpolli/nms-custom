#!/usr/bin/env python3
"""Build the static NCS55A1 chassis-view profile from normalized ENTITY-MIB data."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "docs" / "snmpwalks" / "normalized" / "ncs55a1-entity-mib.json"
FRONTEND_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "ncs55a1"
BACKEND_DIR = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "ncs55a1"
SVG_NAME = "NCS55A1-Front.svg"

WIDTH = 1280
HEIGHT = 430


def component_number(component: dict[str, Any]) -> int:
    return int(component["physicalIndex"])


def port_number(name: str) -> int | None:
    match = re.search(r"0/0/0/(\d+)(?:/\d+)?$", name)
    return int(match.group(1)) if match else None


def clean_port_name(name: str) -> str:
    return name.removeprefix("0/RP0-")


def add_port_links(components: dict[str, dict[str, Any]]) -> None:
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    for component in components.values():
        parent = component.get("containedPhysicalIndex")
        if isinstance(parent, int):
            children_by_parent.setdefault(parent, []).append(component)

    port_components = [
        component
        for component in components.values()
        if component.get("physicalClassLabel") == "port" and port_number(str(component.get("name", ""))) is not None
    ]
    for port in port_components:
        port["ports"] = [
            {
                "id": str(port["physicalIndex"]),
                "name": clean_port_name(str(port["name"])),
                "portId": port["physicalIndex"],
            }
        ]

    for bay in components.values():
        if bay.get("physicalClassLabel") != "container" or "QSFP28 bay" not in str(bay.get("name", "")):
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
            {
                "id": str(port["physicalIndex"]),
                "name": clean_port_name(str(port["name"])),
                "portId": port["physicalIndex"],
            }
            for port in sorted(sibling_ports, key=component_number)
        ]


def find_component(components: dict[str, dict[str, Any]], physical_index: int) -> dict[str, Any]:
    return components[f"component-{physical_index}"]


def hotspot(
    component: dict[str, Any],
    *,
    hotspot_id: str,
    label: str,
    x: float,
    y: float,
    w: float,
    h: float,
    empty: bool = False,
) -> dict[str, Any]:
    return {
        "id": hotspot_id,
        "slotKey": str(component.get("slotKey") or component.get("name") or hotspot_id),
        "label": label,
        "inventoryId": component["id"],
        "physicalIndex": component["physicalIndex"],
        "empty": empty,
        "bounds": {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)},
        "metadata": {
            "sourceName": component.get("name"),
            "sourceTypeId": component.get("typeId"),
            "modelName": component.get("modelName"),
            "modelTypeId": component.get("typeId"),
        },
    }


def build_hotspots(components: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    hotspots: list[dict[str, Any]] = []

    port_w = 58
    port_h = 34
    gap_x = 9
    gap_y = 14
    start_x = 270
    start_y = 86
    for physical_index in range(800, 836):
        bay = find_component(components, physical_index)
        port = physical_index - 800
        row = port // 9
        col = port % 9
        hotspots.append(
            hotspot(
                bay,
                hotspot_id=f"hotspot-qsfp28-{port}",
                label=f"QSFP28 {port}",
                x=start_x + col * (port_w + gap_x),
                y=start_y + row * (port_h + gap_y),
                w=port_w,
                h=port_h,
                empty=len(bay.get("childIds", [])) == 0,
            )
        )

    for physical_index, x in [(4097, 270), (8193, 450)]:
        pm = find_component(components, physical_index)
        hotspots.append(
            hotspot(
                pm,
                hotspot_id=f"hotspot-{pm['name'].replace('/', '-')}",
                label="Power Module",
                x=x,
                y=310,
                w=150,
                h=58,
            )
        )

    for physical_index, y in [(20481, 88), (24577, 178), (28673, 268)]:
        fan = find_component(components, physical_index)
        hotspots.append(
            hotspot(
                fan,
                hotspot_id=f"hotspot-{fan['name'].replace('/', '-')}",
                label="Fan Tray",
                x=960,
                y=y,
                w=170,
                h=62,
            )
        )

    for physical_index, x, y, w, h, label in [
        (1, 54, 86, 156, 184, "Route Processor"),
        (784, 70, 296, 100, 32, "Management Port"),
        (8384513, 38, 52, 1110, 330, "Chassis"),
    ]:
        component = find_component(components, physical_index)
        hotspots.append(
            hotspot(
                component,
                hotspot_id=f"hotspot-{physical_index}",
                label=label,
                x=x,
                y=y,
                w=w,
                h=h,
            )
        )

    return hotspots


def svg_port(x: float, y: float, label: str, populated: bool) -> str:
    fill = "#1d4ed8" if populated else "#1f2937"
    stroke = "#93c5fd" if populated else "#4b5563"
    return (
        f'<g><rect x="{x}" y="{y}" width="58" height="34" rx="4" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"/>'
        f'<rect x="{x + 7}" y="{y + 8}" width="44" height="18" rx="2" fill="#07111f" opacity=".74"/>'
        f'<text x="{x + 29}" y="{y + 56}" text-anchor="middle" font-size="12" fill="#d1d5db">{label}</text></g>'
    )


def build_svg(components: dict[str, dict[str, Any]]) -> str:
    ports: list[str] = []
    port_w = 58
    port_h = 34
    gap_x = 9
    gap_y = 14
    start_x = 270
    start_y = 86
    for port in range(36):
        bay = find_component(components, 800 + port)
        row = port // 9
        col = port % 9
        populated = bool(bay.get("childIds"))
        ports.append(svg_port(start_x + col * (port_w + gap_x), start_y + row * (port_h + gap_y), str(port), populated))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="Cisco NCS55A1 front view">
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
  <rect x="28" y="42" width="1140" height="350" rx="10" fill="url(#metal)" stroke="#6b7280" stroke-width="3"/>
  <rect x="46" y="64" width="1104" height="306" rx="7" fill="url(#face)" stroke="#030712" stroke-width="2"/>
  <text x="70" y="88" font-size="20" font-family="Arial, Helvetica, sans-serif" font-weight="700" fill="#f9fafb">Cisco NCS55A1</text>
  <text x="70" y="112" font-size="13" font-family="Arial, Helvetica, sans-serif" fill="#9ca3af">Fixed 36x100G Scale Route Processor</text>
  <rect x="60" y="132" width="160" height="136" rx="6" fill="#374151" stroke="#6b7280"/>
  <text x="140" y="158" text-anchor="middle" font-size="14" font-family="Arial, Helvetica, sans-serif" fill="#f9fafb">0/RP0</text>
  <circle cx="93" cy="196" r="12" fill="#22c55e"/>
  <circle cx="136" cy="196" r="12" fill="#facc15"/>
  <circle cx="179" cy="196" r="12" fill="#64748b"/>
  <rect x="70" y="296" width="100" height="32" rx="4" fill="#111827" stroke="#60a5fa" stroke-width="2"/>
  <text x="120" y="318" text-anchor="middle" font-size="12" font-family="Arial, Helvetica, sans-serif" fill="#bfdbfe">MGMT</text>
  <rect x="252" y="64" width="620" height="220" rx="6" fill="#111827" stroke="#374151"/>
  <text x="562" y="80" text-anchor="middle" font-size="12" font-family="Arial, Helvetica, sans-serif" fill="#9ca3af">QSFP28 100G ports</text>
  {''.join(ports)}
  <rect x="250" y="292" width="390" height="92" rx="6" fill="#111827" stroke="#374151"/>
  <rect x="270" y="310" width="150" height="58" rx="5" fill="#475569" stroke="#94a3b8"/>
  <rect x="450" y="310" width="150" height="58" rx="5" fill="#475569" stroke="#94a3b8"/>
  <text x="345" y="344" text-anchor="middle" font-size="15" font-family="Arial, Helvetica, sans-serif" fill="#f8fafc">0/PM0</text>
  <text x="525" y="344" text-anchor="middle" font-size="15" font-family="Arial, Helvetica, sans-serif" fill="#f8fafc">0/PM1</text>
  <rect x="930" y="64" width="230" height="306" rx="6" fill="#111827" stroke="#374151"/>
  <text x="1045" y="82" text-anchor="middle" font-size="12" font-family="Arial, Helvetica, sans-serif" fill="#9ca3af">Fan trays</text>
  <g fill="#374151" stroke="#94a3b8" stroke-width="2">
    <rect x="960" y="88" width="170" height="62" rx="5"/>
    <rect x="960" y="178" width="170" height="62" rx="5"/>
    <rect x="960" y="268" width="170" height="62" rx="5"/>
  </g>
  <g font-size="15" font-family="Arial, Helvetica, sans-serif" fill="#f8fafc" text-anchor="middle">
    <text x="1045" y="125">0/FT0</text>
    <text x="1045" y="215">0/FT1</text>
    <text x="1045" y="305">0/FT2</text>
  </g>
</svg>
'''


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    components = source["componentsById"]
    add_port_links(components)

    profile = {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "deviceId": "example-ncs55a1",
        "profileId": "Cisco_NCS55A1",
        "platform": "Cisco NCS55A1",
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": f"/chassis-assets/ncs55a1/{SVG_NAME}",
                "width": WIDTH,
                "height": HEIGHT,
                "sourceWidth": WIDTH,
                "sourceHeight": HEIGHT,
                "hotspots": build_hotspots(components),
            }
        ],
        "tree": source["tree"],
        "componentsById": components,
        "physicalIndexToComponentId": source["physicalIndexToComponentId"],
        "source": {
            "type": "entity-mib-derived-static-profile",
            "profile": str(SOURCE.relative_to(REPO_ROOT)),
        },
    }

    for out_dir in (FRONTEND_DIR, BACKEND_DIR):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / SVG_NAME).write_text(build_svg(components), encoding="utf-8")
        (out_dir / "normalized.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {FRONTEND_DIR / 'normalized.json'}")
    print(f"Wrote {BACKEND_DIR / 'normalized.json'}")


if __name__ == "__main__":
    main()
