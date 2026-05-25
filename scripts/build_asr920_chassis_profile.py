#!/usr/bin/env python3
"""Build the static ASR-920-20SZ-M chassis-view profile.

The Cisco EPNM source profile (figures.tar.gz under
``com.cisco.prime.deviceprofile/NCS42XXFamily/Cisco_ASR-920-20SZ-M_Router/``)
ships a complex 168 KB SVG and a non-strict JSON profile, neither of which is
ideal to embed verbatim. We follow the same hand-curated pattern used for the
NCS55A1 profile: synthesize a sanitized SVG (viewBox 1680x165 — matching the
upstream Cisco asset) and emit a normalized.json that the NMS chassis view can
consume.

The ASR-920-20SZ-M is a 1RU fixed access router with:
  * 20 SFP 1G ports                Gi0/0/0  .. Gi0/0/19  (2 rows of 10)
  * 4  SFP+ 10G uplink ports       Te0/0/20 .. Te0/0/23
  * 1 management port              MgmtEth0
  * 2 power supply bays            PSU 0 / PSU 1
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend" / "public" / "chassis-assets" / "asr920"
BACKEND_DIR = REPO_ROOT / "backend" / "app" / "data" / "chassis" / "asr920"
SVG_NAME = "ASR-920-Front.svg"

# Match upstream EPNM SVG viewBox so coordinates are portable.
WIDTH = 1680
HEIGHT = 165

# Front-panel geometry (SVG units).
CHASSIS_X = 12
CHASSIS_Y = 8
CHASSIS_W = 1656
CHASSIS_H = 149

MGMT_X = 60
MGMT_Y = 56
MGMT_W = 70
MGMT_H = 50

SFP_PORT_W = 46
SFP_PORT_H = 38
SFP_GAP_X = 8
SFP_GAP_Y = 12
SFP_START_X = 200
SFP_START_Y = 36

# 10G uplinks are slightly taller cages on the right.
UPLINK_W = 56
UPLINK_H = 48
UPLINK_GAP_X = 8
UPLINK_START_X = 1132
UPLINK_START_Y = 56

PSU_W = 138
PSU_H = 98
PSU_GAP = 14
PSU_START_X = 1390
PSU_START_Y = 34

SFP_PORT_COUNT = 20
SFP_ROW_COUNT = 2
SFP_COLS = SFP_PORT_COUNT // SFP_ROW_COUNT
UPLINK_COUNT = 4
PSU_COUNT = 2


def sfp_bounds(port: int) -> tuple[float, float, float, float]:
    row = port // SFP_COLS
    col = port % SFP_COLS
    x = SFP_START_X + col * (SFP_PORT_W + SFP_GAP_X)
    y = SFP_START_Y + row * (SFP_PORT_H + SFP_GAP_Y)
    return x, y, SFP_PORT_W, SFP_PORT_H


def uplink_bounds(idx: int) -> tuple[float, float, float, float]:
    x = UPLINK_START_X + idx * (UPLINK_W + UPLINK_GAP_X)
    return x, UPLINK_START_Y, UPLINK_W, UPLINK_H


def psu_bounds(idx: int) -> tuple[float, float, float, float]:
    x = PSU_START_X + idx * (PSU_W + PSU_GAP)
    return x, PSU_START_Y, PSU_W, PSU_H


# --- Component model ----------------------------------------------------------
# Synthetic physicalIndex space for the static profile. Live ENTITY-MIB merge
# matches by these numeric indices via physicalIndexToComponentId.
PIDX_CHASSIS = 1
PIDX_RP = 10
PIDX_MGMT = 11
PIDX_PSU_BAY = (20, 21)
PIDX_PSU_MOD = (22, 23)
# SFP cage bays start at 100, transceivers at 200, ports at 300.
PIDX_SFP_BAY_BASE = 100
PIDX_SFP_PORT_BASE = 300
# 10G uplink cages start at 150, ports at 350.
PIDX_UPLINK_BAY_BASE = 150
PIDX_UPLINK_PORT_BASE = 350


def cid(idx: int) -> str:
    return f"component-{idx}"


def build_components() -> tuple[dict[str, dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    components: dict[str, dict[str, Any]] = {}
    physical_index_map: dict[str, str] = {}

    def add(
        *,
        physical_index: int,
        name: str,
        description: str,
        type_: str,
        parent_index: int | None,
        type_id: str | None = None,
        ports: list[dict[str, Any]] | None = None,
        child_indices: list[int] | None = None,
        oper_status: str | None = None,
    ) -> dict[str, Any]:
        comp_id = cid(physical_index)
        component: dict[str, Any] = {
            "id": comp_id,
            "name": name,
            "displayName": name,
            "description": description,
            "type": type_,
            "physicalIndex": physical_index,
            "sourceId": physical_index,
            "ports": ports or [],
            "childIds": [cid(c) for c in (child_indices or [])],
            "serviceState": 1,
        }
        if parent_index is not None:
            component["parentId"] = cid(parent_index)
            component["containedPhysicalIndex"] = parent_index
        if type_id:
            component["typeId"] = type_id
        if oper_status:
            component["operStatus"] = oper_status
        components[comp_id] = component
        physical_index_map[str(physical_index)] = comp_id
        return component

    # SFP cage bays + transceiver containers + ports.
    sfp_bay_children: list[int] = []
    for port in range(SFP_PORT_COUNT):
        bay_idx = PIDX_SFP_BAY_BASE + port
        port_idx = PIDX_SFP_PORT_BASE + port
        port_name = f"GigabitEthernet0/0/{port}"
        add(
            physical_index=port_idx,
            name=port_name,
            description="GE SFP port",
            type_="Module",
            parent_index=bay_idx,
            type_id="SFP-GE-T",
            oper_status="down",
            ports=[{"id": str(port_idx), "name": port_name, "portId": port_idx}],
        )
        add(
            physical_index=bay_idx,
            name=f"subslot 0/0 transceiver container {port}",
            description="SFP cage",
            type_="Equipment",
            parent_index=PIDX_CHASSIS,
            child_indices=[port_idx],
        )
        sfp_bay_children.append(bay_idx)

    # 10G uplink cages.
    uplink_bay_children: list[int] = []
    for idx in range(UPLINK_COUNT):
        bay_idx = PIDX_UPLINK_BAY_BASE + idx
        port_idx = PIDX_UPLINK_PORT_BASE + idx
        port_no = SFP_PORT_COUNT + idx
        port_name = f"TenGigabitEthernet0/0/{port_no}"
        add(
            physical_index=port_idx,
            name=port_name,
            description="10GE SFP+ uplink",
            type_="Module",
            parent_index=bay_idx,
            type_id="SFP-10G-SR",
            oper_status="down",
            ports=[{"id": str(port_idx), "name": port_name, "portId": port_idx}],
        )
        add(
            physical_index=bay_idx,
            name=f"subslot 0/0 transceiver container {port_no}",
            description="SFP+ cage",
            type_="Equipment",
            parent_index=PIDX_CHASSIS,
            child_indices=[port_idx],
        )
        uplink_bay_children.append(bay_idx)

    # Mgmt port.
    add(
        physical_index=PIDX_MGMT,
        name="MgmtEth0/RP0/CPU0/0",
        description="Management Ethernet",
        type_="Module",
        parent_index=PIDX_RP,
        type_id="RJ45",
        oper_status="up",
        ports=[{"id": str(PIDX_MGMT), "name": "MgmtEth0/RP0/CPU0/0", "portId": PIDX_MGMT}],
    )

    # Route processor (built-in for 1RU 920).
    add(
        physical_index=PIDX_RP,
        name="module 0/RP0/CPU0",
        description="Route Processor",
        type_="Module",
        parent_index=PIDX_CHASSIS,
        type_id="ASR-920-20SZ-M-RP",
        oper_status="up",
        child_indices=[PIDX_MGMT],
    )

    # Power supplies.
    for slot, (bay_idx, mod_idx) in enumerate(zip(PIDX_PSU_BAY, PIDX_PSU_MOD)):
        add(
            physical_index=mod_idx,
            name=f"Power Supply Module {slot}",
            description="ASR 920 250W AC Power Supply",
            type_="Equipment",
            parent_index=bay_idx,
            type_id="ASR-920-PWR-A",
            oper_status="on",
        )
        add(
            physical_index=bay_idx,
            name=f"Power Supply Bay {slot}",
            description="Power Supply Bay",
            type_="Equipment",
            parent_index=PIDX_CHASSIS,
            child_indices=[mod_idx],
        )

    # Chassis root.
    chassis_children = (
        [PIDX_RP]
        + sfp_bay_children
        + uplink_bay_children
        + list(PIDX_PSU_BAY)
    )
    chassis = add(
        physical_index=PIDX_CHASSIS,
        name="Chassis",
        description="Cisco ASR-920-20SZ-M Router Chassis",
        type_="Chassis",
        parent_index=None,
        type_id="ASR-920-20SZ-M",
        child_indices=chassis_children,
    )
    chassis["manufacturer"] = "Cisco Systems Inc"
    chassis["hardwareVersion"] = "V01"
    chassis["isFRUable"] = "TRUE"

    # Tree (depth-first).
    def node(physical_index: int) -> dict[str, Any]:
        comp = components[cid(physical_index)]
        return {
            "id": comp["id"],
            "componentId": comp["id"],
            "label": comp["displayName"],
            "physicalIndex": comp["physicalIndex"] if comp["physicalIndex"] != PIDX_CHASSIS else None,
            "type": comp["type"],
            "typeId": comp.get("typeId"),
            "children": [node(int(c.split("-", 1)[1])) for c in comp["childIds"]],
        }

    tree = [node(PIDX_CHASSIS)]
    # Match the convention in other profiles: chassis root physicalIndex is null.
    tree[0]["physicalIndex"] = None
    return components, physical_index_map, tree


def build_hotspots() -> list[dict[str, Any]]:
    hotspots: list[dict[str, Any]] = []

    def hotspot(
        *,
        hotspot_id: str,
        label: str,
        component_index: int,
        x: float,
        y: float,
        w: float,
        h: float,
        slot_key: str,
        empty: bool = False,
        type_id: str | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": hotspot_id,
            "slotKey": slot_key,
            "label": label,
            "inventoryId": cid(component_index),
            "physicalIndex": component_index,
            "empty": empty,
            "bounds": {"x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2)},
            "metadata": {
                "sourceName": label,
                "sourceTypeId": type_id,
                "modelName": model_name or label,
                "modelTypeId": type_id,
            },
        }

    # SFP 1G ports.
    for port in range(SFP_PORT_COUNT):
        x, y, w, h = sfp_bounds(port)
        hotspots.append(
            hotspot(
                hotspot_id=f"hotspot-sfp-{port}",
                label=f"Gi0/0/{port}",
                component_index=PIDX_SFP_PORT_BASE + port,
                x=x, y=y, w=w, h=h,
                slot_key=f"subslot/0/0/{port}",
                type_id="SFP-GE-T",
                model_name="SFP Gigabit Ethernet",
            )
        )

    # 10G uplinks.
    for idx in range(UPLINK_COUNT):
        x, y, w, h = uplink_bounds(idx)
        port_no = SFP_PORT_COUNT + idx
        hotspots.append(
            hotspot(
                hotspot_id=f"hotspot-uplink-{port_no}",
                label=f"Te0/0/{port_no}",
                component_index=PIDX_UPLINK_PORT_BASE + idx,
                x=x, y=y, w=w, h=h,
                slot_key=f"subslot/0/0/{port_no}",
                type_id="SFP-10G-SR",
                model_name="SFP+ 10G uplink",
            )
        )

    # Mgmt port.
    hotspots.append(
        hotspot(
            hotspot_id="hotspot-mgmt",
            label="MgmtEth",
            component_index=PIDX_MGMT,
            x=MGMT_X, y=MGMT_Y, w=MGMT_W, h=MGMT_H,
            slot_key="mgmt0",
            type_id="RJ45",
            model_name="Management Ethernet",
        )
    )

    # Power supplies.
    for idx, (bay_idx, mod_idx) in enumerate(zip(PIDX_PSU_BAY, PIDX_PSU_MOD)):
        x, y, w, h = psu_bounds(idx)
        hotspots.append(
            hotspot(
                hotspot_id=f"hotspot-psu-{idx}",
                label=f"PSU {idx}",
                component_index=mod_idx,
                x=x, y=y, w=w, h=h,
                slot_key=f"Power_Supply_Bay_{idx}",
                type_id="ASR-920-PWR-A",
                model_name="ASR 920 250W AC PSU",
            )
        )

    return hotspots


def svg_sfp_port(x: float, y: float, label: str) -> str:
    return (
        f'<g><rect x="{x}" y="{y}" width="{SFP_PORT_W}" height="{SFP_PORT_H}" rx="3" '
        f'fill="#1f2937" stroke="#4b5563" stroke-width="1.5"/>'
        f'<rect x="{x + 5}" y="{y + 7}" width="{SFP_PORT_W - 10}" height="{SFP_PORT_H - 16}" rx="2" '
        f'fill="#07111f" opacity=".82"/>'
        f'<text x="{x + SFP_PORT_W / 2}" y="{y + SFP_PORT_H - 4}" text-anchor="middle" '
        f'font-size="9" fill="#cbd5f5">{label}</text></g>'
    )


def svg_uplink_port(x: float, y: float, label: str) -> str:
    return (
        f'<g><rect x="{x}" y="{y}" width="{UPLINK_W}" height="{UPLINK_H}" rx="4" '
        f'fill="#1d4ed8" stroke="#93c5fd" stroke-width="1.5"/>'
        f'<rect x="{x + 7}" y="{y + 10}" width="{UPLINK_W - 14}" height="{UPLINK_H - 22}" rx="2" '
        f'fill="#07111f" opacity=".78"/>'
        f'<text x="{x + UPLINK_W / 2}" y="{y + UPLINK_H - 4}" text-anchor="middle" '
        f'font-size="9" fill="#dbeafe">{label}</text></g>'
    )


def build_svg() -> str:
    sfp_glyphs = [
        svg_sfp_port(*sfp_bounds(port)[:2], f"{port}") for port in range(SFP_PORT_COUNT)
    ]
    uplink_glyphs = [
        svg_uplink_port(*uplink_bounds(idx)[:2], f"Te{SFP_PORT_COUNT + idx}")
        for idx in range(UPLINK_COUNT)
    ]
    psu_glyphs = []
    for idx in range(PSU_COUNT):
        x, y, w, h = psu_bounds(idx)
        psu_glyphs.append(
            f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="#475569" '
            f'stroke="#94a3b8" stroke-width="1.5"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 5}" text-anchor="middle" font-size="14" '
            f'fill="#f8fafc">PSU {idx}</text></g>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" '
        f'aria-label="Cisco ASR-920-20SZ-M front view">'
        f'<defs>'
        f'<linearGradient id="face920" x1="0" x2="1">'
        f'<stop offset="0" stop-color="#111827"/>'
        f'<stop offset=".55" stop-color="#1f2937"/>'
        f'<stop offset="1" stop-color="#0f172a"/>'
        f'</linearGradient>'
        f'<linearGradient id="metal920" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="#e5e7eb"/>'
        f'<stop offset="1" stop-color="#9ca3af"/>'
        f'</linearGradient>'
        f'</defs>'
        f'<rect x="{CHASSIS_X}" y="{CHASSIS_Y}" width="{CHASSIS_W}" height="{CHASSIS_H}" rx="6" '
        f'fill="url(#metal920)" stroke="#6b7280" stroke-width="2"/>'
        f'<rect x="{CHASSIS_X + 6}" y="{CHASSIS_Y + 6}" width="{CHASSIS_W - 12}" height="{CHASSIS_H - 12}" '
        f'rx="4" fill="url(#face920)" stroke="#030712" stroke-width="1.5"/>'
        f'<text x="22" y="28" font-size="14" font-family="Arial, Helvetica, sans-serif" '
        f'font-weight="700" fill="#f9fafb">Cisco ASR-920-20SZ-M</text>'
        f'<text x="22" y="44" font-size="9" font-family="Arial, Helvetica, sans-serif" '
        f'fill="#9ca3af">20x SFP / 4x SFP+ access router</text>'
        f'<rect x="{MGMT_X}" y="{MGMT_Y}" width="{MGMT_W}" height="{MGMT_H}" rx="4" '
        f'fill="#111827" stroke="#60a5fa" stroke-width="1.5"/>'
        f'<text x="{MGMT_X + MGMT_W / 2}" y="{MGMT_Y + MGMT_H / 2 + 4}" text-anchor="middle" '
        f'font-size="11" fill="#bfdbfe">MGMT</text>'
        + "".join(sfp_glyphs)
        + "".join(uplink_glyphs)
        + "".join(psu_glyphs)
        + "</svg>"
    )


def main() -> None:
    components, physical_index_map, tree = build_components()

    profile = {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "deviceId": "sample-asr920",
        "profileId": "Cisco_ASR_920_20SZ_M_Router",
        "platform": "Cisco ASR-920-20SZ-M Router",
        "model": "ASR-920-20SZ-M",
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": f"/chassis-assets/asr920/{SVG_NAME}",
                "width": WIDTH,
                "height": HEIGHT,
                "sourceWidth": WIDTH,
                "sourceHeight": HEIGHT,
                "sourceImage": (
                    "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
                    "NCS42XXFamily/Cisco_ASR-920-20SZ-M_Router/images/"
                    "ASR-920-20SZ-M-Front-Core.svg"
                ),
                "hotspots": build_hotspots(),
            }
        ],
        "tree": tree,
        "componentsById": components,
        "physicalIndexToComponentId": physical_index_map,
        "source": {
            "type": "hand-curated-static-profile",
            "package": ".local/chassis-assets/figures.tar.gz",
            "profile": (
                "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
                "NCS42XXFamily/Cisco_ASR-920-20SZ-M_Router/data/"
                "Cisco_ASR-920-20SZ-M_Router.json"
            ),
            "image": (
                "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
                "NCS42XXFamily/Cisco_ASR-920-20SZ-M_Router/images/"
                "ASR-920-20SZ-M-Front-Core.svg"
            ),
        },
    }

    svg = build_svg()

    for out_dir in (FRONTEND_DIR, BACKEND_DIR):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / SVG_NAME).write_text(svg, encoding="utf-8")
        (out_dir / "normalized.json").write_text(
            json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    print(f"Wrote {FRONTEND_DIR / 'normalized.json'}")
    print(f"Wrote {BACKEND_DIR / 'normalized.json'}")


if __name__ == "__main__":
    main()
