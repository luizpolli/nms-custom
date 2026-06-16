#!/usr/bin/env python3
"""Build static chassis-view profiles for ASR920 variants.

Generates ``asr920-12cz`` (ASR-920-12CZ-A/D), ``asr920-12sz``
(ASR-920-12SZ-A/D), ``asr920-12sz-im`` (ASR-920-12SZ-IM / -CC / 920U) and
``asr920-24sz`` (ASR-920-24SZ-M, 24xGE fiber + 4x10G, modular PSU) following
the hand-curated pattern of the existing ASR-920-20SZ-M profile
(scripts/archive/chassis-migration/build_asr920_chassis_profile.py), with one
key difference: every component carries the REAL entPhysicalIndex observed in
the reference walks under ``docs/snmpwalks/asr920/``, so live ENTITY-MIB
collections and alarms map 1:1 onto the chassis figure.

Index scheme confirmed against the walks:
  * chassis=1, slot R0=2, subslot 0/0=3, RP module=100
  * fixed ethernet module = 300
  * copper RJ45 ports Gi0/0/0..7         -> 301 + N
  * SFP transceiver container N          -> 359 + 14*N
  * SFP port (when optic present)        -> container + 2
    (verified: Gi0/0/11=515, Te0/0/12=529, Te0/0/13=543, Te0/0/0=361)
  * PSU bays / modules and fan tray indexes differ per variant (see VARIANTS)

Run:  python3 scripts/build_asr920_variant_profiles.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_ASSET_BASE = "/chassis-assets/asr920/modules"

WIDTH = 1680
HEIGHT = 165
CHASSIS_X, CHASSIS_Y, CHASSIS_W, CHASSIS_H = 12, 8, 1656, 149

PORT_W, PORT_H = 46, 38
PORT_GAP_X, PORT_GAP_Y = 8, 12
GE_START_X, GE_START_Y = 200, 36
GE_COLS = 6

UPLINK_W, UPLINK_H = 56, 48
UPLINK_GAP_X = 8
UPLINK_START_X, UPLINK_START_Y = 560, 56

IM_X, IM_Y, IM_W, IM_H = 860, 34, 360, 98
FAN_X, FAN_Y, FAN_W, FAN_H = 22, 96, 130, 50

PSU_W, PSU_H = 138, 98
PSU_GAP = 14
PSU_START_X, PSU_START_Y = 1390, 34


def sfp_container_index(port: int) -> int:
    return 359 + 14 * port


def sfp_port_index(port: int) -> int:
    return sfp_container_index(port) + 2


VARIANTS: dict[str, dict[str, Any]] = {
    "asr920-12cz": {
        "profileId": "Cisco_ASR_920_12CZ_Router",
        "platform": "Cisco ASR-920-12CZ Router",
        "model": "ASR-920-12CZ-D",
        "subtitle": "8x RJ45 GE + 4x SFP GE / 2x SFP+ 10G access router",
        "moduleModel": "12xGE-2x10GE-FIXED",
        "moduleDescr": "FIXED : 12-port Gig & 2-port Ten Gig Dual Ethernet",
        "copperPorts": list(range(0, 8)),
        "sfpGePorts": list(range(8, 12)),
        "uplinkPorts": list(range(12, 14)),
        "psuBays": (4, 24),
        "psuModules": (5, 25),
        "fanTray": 45,
        "fanBay": None,
        "imBay": None,
        "psuTypeId": "ASR-920-PWR-D",
        "psuDescr": "ASR 920 250W DC Power Supply",
        "sourceProfile": (
            "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
            "NCS42XXFamily/Cisco_ASR920_12_CZ_D_Router"
        ),
        "walk": "docs/snmpwalks/asr920/entPhysicalASR920-12CZ-D.walk",
    },
    "asr920-12sz": {
        "profileId": "Cisco_ASR_920_12SZ_Router",
        "platform": "Cisco ASR-920-12SZ Router",
        "model": "ASR-920-12SZ-D",
        "subtitle": "12x dual-rate 1G/10G SFP+ access router",
        "moduleModel": "12x10GE-FIXED",
        "moduleDescr": "FIXED : 12-port dual rate 10G/1G Ethernet",
        "copperPorts": [],
        "sfpGePorts": [],
        "dualRatePorts": list(range(0, 12)),
        "uplinkPorts": [],
        "psuBays": (4, 24),
        "psuModules": (5, 25),
        "fanTray": 45,
        "fanBay": None,
        "imBay": None,
        "psuTypeId": "ASR-920-PWR-D",
        "psuDescr": "ASR 920 250W DC Power Supply",
        "sourceProfile": (
            "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
            "NCS42XXFamily/Cisco_ASR920-12SZ-D_Router"
        ),
        "walk": "docs/snmpwalks/asr920/entPhysicalASR920-12SZ-D.walk",
    },
    "asr920-12sz-im": {
        "profileId": "Cisco_ASR_920_12SZ_IM_Router",
        "platform": "Cisco ASR-920-12SZ-IM Router",
        "model": "ASR-920-12SZ-IM",
        "subtitle": "8x RJ45 GE + 4x SFP GE / 4x SFP+ 10G + IM slot access router",
        "moduleModel": "12xGE-4x10GE-FIXED",
        "moduleDescr": "FIXED : 12-port Gig & 4-port Ten Gig Ethernet",
        "copperPorts": list(range(0, 8)),
        "sfpGePorts": list(range(8, 12)),
        "uplinkPorts": list(range(12, 16)),
        "psuBays": (5, 25),
        "psuModules": (6, 26),
        "fanTray": 46,
        "fanBay": 45,
        "imBay": 4,
        "psuTypeId": "ASR-920-PWR-A",
        "psuDescr": "ASR 920 250W AC Power Supply",
        "sourceProfile": (
            "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
            "NCS42XXFamily/Cisco_ASR_920-12SZ-IM_Router"
        ),
        "walk": "docs/snmpwalks/asr920/entPhysicalASR920-12SZ-IM.walk",
    },
    "asr920-24sz": {
        "profileId": "Cisco_ASR_920_24SZM_Router",
        "platform": "Cisco ASR-920-24SZ-M Router",
        "model": "ASR-920-24SZ-M",
        "subtitle": "24x GE SFP + 4x 10G SFP+ access router",
        "moduleModel": "24xGE-4x10GE-FIXED-S",
        "moduleDescr": (
            "FIXED : 24-port Gig & 4-port Ten Gig SFP Ethernet Interface Module"
        ),
        "copperPorts": [],
        "sfpGePorts": list(range(0, 24)),
        "uplinkPorts": list(range(24, 28)),
        "psuBays": (5, 25),
        "psuModules": (6, 26),
        "fanTray": 46,
        "fanBay": 45,
        "imBay": None,
        "psuTypeId": "ASR-920-PWR-D",
        "psuDescr": "ASR 920 250W DC Power Supply",
        "sourceProfile": (
            "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/"
            "NCS42XXFamily/Cisco_ASR_920_24SZM_Router"
        ),
        "walk": "docs/snmpwalks/asr920/entPhysicalASR920-24SZ.walk",
    },
}


def cid(idx: int) -> str:
    return f"component-{idx}"


def ge_bounds(slot: int) -> tuple[float, float, float, float]:
    row, col = slot // GE_COLS, slot % GE_COLS
    x = GE_START_X + col * (PORT_W + PORT_GAP_X)
    y = GE_START_Y + row * (PORT_H + PORT_GAP_Y)
    return x, y, PORT_W, PORT_H


def uplink_bounds(idx: int, total: int) -> tuple[float, float, float, float]:
    if total <= 2:
        x = UPLINK_START_X + idx * (UPLINK_W + UPLINK_GAP_X)
        return x, UPLINK_START_Y, UPLINK_W, UPLINK_H
    row, col = idx // 2, idx % 2
    x = UPLINK_START_X + col * (UPLINK_W + UPLINK_GAP_X)
    y = GE_START_Y + row * (PORT_H + PORT_GAP_Y)
    return x, y, UPLINK_W, PORT_H


def psu_bounds(idx: int) -> tuple[float, float, float, float]:
    return PSU_START_X + idx * (PSU_W + PSU_GAP), PSU_START_Y, PSU_W, PSU_H


class ProfileBuilder:
    def __init__(self, name: str, spec: dict[str, Any]):
        self.name = name
        self.spec = spec
        self.components: dict[str, dict[str, Any]] = {}
        self.physical_index_map: dict[str, str] = {}
        self.hotspots: list[dict[str, Any]] = []
        self.svg_glyphs: list[str] = []

    def add_component(
        self,
        *,
        physical_index: int,
        name: str,
        description: str,
        type_: str,
        parent_index: int | None,
        type_id: str | None = None,
        model_name: str | None = None,
        ports: list[dict[str, Any]] | None = None,
        child_indices: list[int] | None = None,
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
        component["modelName"] = model_name or description
        self.components[comp_id] = component
        self.physical_index_map[str(physical_index)] = comp_id
        return component

    def add_port_component(self, physical_index: int, port_name: str, description: str,
                           type_id: str, parent_index: int) -> None:
        self.add_component(
            physical_index=physical_index,
            name=port_name,
            description=description,
            type_="Port",
            parent_index=parent_index,
            type_id=type_id,
            ports=[{"id": str(physical_index), "name": port_name, "portId": physical_index}],
        )

    def add_hotspot(self, *, hotspot_id: str, label: str, component_index: int,
                    bounds: tuple[float, float, float, float], slot_key: str,
                    type_id: str | None = None, model_name: str | None = None,
                    asset_image: str | None = None, empty: bool = False) -> None:
        x, y, w, h = bounds
        hotspot: dict[str, Any] = {
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
        if asset_image:
            hotspot["asset"] = {
                "typeId": type_id or "SFP",
                "image": asset_image,
                "sourceImage": asset_image,
            }
        self.hotspots.append(hotspot)

    # ── SVG glyphs (same visual language as the shipped asr920 profile) ──────
    def glyph_port(self, bounds: tuple[float, float, float, float], label: str,
                   fill: str, stroke: str, text: str) -> None:
        x, y, w, h = bounds
        self.svg_glyphs.append(
            f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<rect x="{x + 5}" y="{y + 7}" width="{w - 10}" height="{h - 16}" rx="2" '
            f'fill="#07111f" opacity=".82"/>'
            f'<text x="{x + w / 2}" y="{y + h - 4}" text-anchor="middle" '
            f'font-size="9" fill="{text}">{label}</text></g>'
        )

    def glyph_box(self, bounds: tuple[float, float, float, float], label: str,
                  fill: str, stroke: str, font_size: int = 14) -> None:
        x, y, w, h = bounds
        self.svg_glyphs.append(
            f'<g><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 5}" text-anchor="middle" '
            f'font-size="{font_size}" fill="#f8fafc">{label}</text></g>'
        )

    def build(self) -> tuple[dict[str, Any], str]:
        spec = self.spec
        chassis_children: list[int] = [2]
        fixed_children: list[int] = []

        # RP / control plane.
        self.add_component(
            physical_index=2, name="slot R0", description="Route Processor Slot",
            type_="Equipment", parent_index=1, child_indices=[100],
        )
        self.add_component(
            physical_index=100, name="module R0",
            description=f"{spec['platform']} Route Switch Processor",
            type_="Module", parent_index=2,
            type_id=spec["model"], model_name=spec["model"],
        )

        # Fixed ethernet module under subslot 0/0.
        chassis_children.append(3)
        self.add_component(
            physical_index=3, name="subslot 0/0", description="FIXED IM Bay",
            type_="Equipment", parent_index=1, child_indices=[300],
        )

        # Copper RJ45 ports.
        for port in spec.get("copperPorts", []):
            idx = 301 + port
            name = f"GigabitEthernet0/0/{port}"
            self.add_port_component(idx, name, "GE RJ45 port", "RJ45-GE", 300)
            fixed_children.append(idx)
            self.add_hotspot(
                hotspot_id=f"hotspot-rj45-{port}", label=f"Gi0/0/{port}",
                component_index=idx, bounds=ge_bounds(port),
                slot_key=f"subslot/0/0/{port}", type_id="RJ45-GE",
                model_name="GE RJ45 port",
                asset_image=f"{MODULE_ASSET_BASE}/GLC.svg",
            )
            self.glyph_port(ge_bounds(port), f"{port}", "#374151", "#6b7280", "#e5e7eb")

        # GE SFP ports (container + port, real indexes).
        for port in spec.get("sfpGePorts", []):
            self._add_sfp(port, f"GigabitEthernet0/0/{port}", "GE SFP port", "SFP-GE",
                          ge_bounds(port), f"hotspot-sfp-{port}", f"Gi0/0/{port}")
            fixed_children.append(sfp_container_index(port))
            self.glyph_port(ge_bounds(port), f"{port}", "#1f2937", "#4b5563", "#cbd5f5")

        # Dual-rate SFP+ ports (12SZ).
        for port in spec.get("dualRatePorts", []):
            self._add_sfp(port, f"TenGigabitEthernet0/0/{port}", "1G/10G dual-rate SFP+ port",
                          "SFP-10G", ge_bounds(port), f"hotspot-sfp-{port}", f"Te0/0/{port}")
            fixed_children.append(sfp_container_index(port))
            self.glyph_port(ge_bounds(port), f"{port}", "#1e3a5f", "#3b82f6", "#bfdbfe")

        # 10G uplinks.
        uplinks = spec.get("uplinkPorts", [])
        for pos, port in enumerate(uplinks):
            bounds = uplink_bounds(pos, len(uplinks))
            self._add_sfp(port, f"TenGigabitEthernet0/0/{port}", "10GE SFP+ uplink",
                          "SFP-10G", bounds, f"hotspot-uplink-{port}", f"Te0/0/{port}")
            fixed_children.append(sfp_container_index(port))
            self.glyph_port(bounds, f"Te{port}", "#1d4ed8", "#93c5fd", "#dbeafe")

        self.add_component(
            physical_index=300, name=" FIXED IM subslot 0/0",
            description=spec["moduleDescr"], type_="Module", parent_index=3,
            type_id=spec["moduleModel"], model_name=spec["moduleModel"],
            child_indices=fixed_children,
        )

        # IM bay (12SZ-IM only).
        if spec.get("imBay") is not None:
            im_idx = spec["imBay"]
            chassis_children.append(im_idx)
            self.add_component(
                physical_index=im_idx, name="subslot 0/1",
                description="Interface Module Bay", type_="Equipment", parent_index=1,
            )
            self.add_hotspot(
                hotspot_id="hotspot-im-0", label="IM 0/1", component_index=im_idx,
                bounds=(IM_X, IM_Y, IM_W, IM_H), slot_key="subslot/0/1",
                model_name="Interface Module Bay", empty=True,
            )
            self.glyph_box((IM_X, IM_Y, IM_W, IM_H), "IM SLOT 0/1", "#111827", "#475569")

        # Power supplies.
        for slot, (bay_idx, mod_idx) in enumerate(
            zip(spec["psuBays"], spec["psuModules"], strict=True)
        ):
            self.add_component(
                physical_index=mod_idx, name=f"Power Supply Module {slot}",
                description=spec["psuDescr"], type_="Equipment", parent_index=bay_idx,
                type_id=spec["psuTypeId"], model_name=spec["psuTypeId"],
            )
            self.add_component(
                physical_index=bay_idx, name=f"Power Supply Bay {slot}",
                description="Power Supply Bay", type_="Equipment", parent_index=1,
                child_indices=[mod_idx],
            )
            chassis_children.append(bay_idx)
            self.add_hotspot(
                hotspot_id=f"hotspot-psu-{slot}", label=f"PSU {slot}",
                component_index=mod_idx, bounds=psu_bounds(slot),
                slot_key=f"Power_Supply_Bay_{slot}", type_id=spec["psuTypeId"],
                model_name=spec["psuDescr"],
                asset_image=f"{MODULE_ASSET_BASE}/{spec['psuTypeId']}.svg",
            )
            self.glyph_box(psu_bounds(slot), f"PSU {slot}", "#475569", "#94a3b8")

        # Fan tray (optionally inside a fan bay, as on the 12SZ-IM).
        fan_parent = 1
        if spec.get("fanBay") is not None:
            fan_bay = spec["fanBay"]
            self.add_component(
                physical_index=fan_bay, name="Fan Tray Bay 0", description="Fan Tray Bay",
                type_="Equipment", parent_index=1, child_indices=[spec["fanTray"]],
            )
            chassis_children.append(fan_bay)
            fan_parent = fan_bay
        else:
            chassis_children.append(spec["fanTray"])
        self.add_component(
            physical_index=spec["fanTray"], name="Fan Tray",
            description="ASR 920 Fan tray", type_="Equipment", parent_index=fan_parent,
            type_id="ASR-920-FAN", model_name="ASR-920-FAN",
        )
        self.add_hotspot(
            hotspot_id="hotspot-fan-0", label="Fan Tray",
            component_index=spec["fanTray"], bounds=(FAN_X, FAN_Y, FAN_W, FAN_H),
            slot_key="Fan_Tray_0", type_id="ASR-920-FAN", model_name="ASR 920 Fan tray",
        )
        self.glyph_box((FAN_X, FAN_Y, FAN_W, FAN_H), "FAN", "#1f2937", "#4b5563", 11)

        # Chassis root.
        chassis = self.add_component(
            physical_index=1, name="Chassis",
            description=f"{spec['platform']} Chassis", type_="Chassis",
            parent_index=None, type_id=spec["model"], model_name=spec["model"],
            child_indices=sorted(set(chassis_children)),
        )
        chassis["manufacturer"] = "Cisco Systems Inc"
        chassis["isFRUable"] = "TRUE"

        return self._emit()

    def _add_sfp(self, port: int, port_name: str, description: str, type_id: str,
                 bounds: tuple[float, float, float, float], hotspot_id: str,
                 label: str) -> None:
        container_idx = sfp_container_index(port)
        port_idx = sfp_port_index(port)
        self.add_port_component(port_idx, port_name, description, type_id, container_idx)
        self.add_component(
            physical_index=container_idx,
            name=f"subslot 0/0 transceiver container {port}",
            description="SFP cage", type_="Equipment", parent_index=300,
            child_indices=[port_idx],
        )
        self.add_hotspot(
            hotspot_id=hotspot_id, label=label, component_index=port_idx,
            bounds=bounds, slot_key=f"subslot/0/0/{port}", type_id=type_id,
            model_name=description, asset_image=f"{MODULE_ASSET_BASE}/SFP.svg",
        )

    def _tree(self) -> list[dict[str, Any]]:
        def node(physical_index: int) -> dict[str, Any]:
            comp = self.components[cid(physical_index)]
            return {
                "id": comp["id"],
                "componentId": comp["id"],
                "label": comp["displayName"],
                "physicalIndex": None if physical_index == 1 else comp["physicalIndex"],
                "type": comp["type"],
                "typeId": comp.get("typeId"),
                "children": [node(int(c.split("-", 1)[1])) for c in comp["childIds"]],
            }

        return [node(1)]

    def _svg(self) -> str:
        spec = self.spec
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
            f'width="{WIDTH}" height="{HEIGHT}" role="img" '
            f'aria-label="{spec["platform"]} front view">'
            f'<defs>'
            f'<linearGradient id="face920v" x1="0" x2="1">'
            f'<stop offset="0" stop-color="#111827"/>'
            f'<stop offset=".55" stop-color="#1f2937"/>'
            f'<stop offset="1" stop-color="#0f172a"/>'
            f'</linearGradient>'
            f'<linearGradient id="metal920v" x1="0" x2="0" y1="0" y2="1">'
            f'<stop offset="0" stop-color="#e5e7eb"/>'
            f'<stop offset="1" stop-color="#9ca3af"/>'
            f'</linearGradient>'
            f'</defs>'
            f'<rect x="{CHASSIS_X}" y="{CHASSIS_Y}" width="{CHASSIS_W}" height="{CHASSIS_H}" '
            f'rx="6" fill="url(#metal920v)" stroke="#6b7280" stroke-width="2"/>'
            f'<rect x="{CHASSIS_X + 6}" y="{CHASSIS_Y + 6}" width="{CHASSIS_W - 12}" '
            f'height="{CHASSIS_H - 12}" rx="4" fill="url(#face920v)" stroke="#030712" '
            f'stroke-width="1.5"/>'
            f'<text x="22" y="28" font-size="14" font-family="Arial, Helvetica, sans-serif" '
            f'font-weight="700" fill="#f9fafb">{spec["platform"]}</text>'
            f'<text x="22" y="44" font-size="9" font-family="Arial, Helvetica, sans-serif" '
            f'fill="#9ca3af">{spec["subtitle"]}</text>'
            + "".join(self.svg_glyphs)
            + "</svg>"
        )

    def _emit(self) -> tuple[dict[str, Any], str]:
        spec = self.spec
        svg_name = f"{spec['model']}-Front.svg"
        profile = {
            "schemaVersion": "nms.chassisView.v1",
            "generatedAt": datetime.now(UTC).isoformat(),
            "deviceId": f"sample-{self.name}",
            "profileId": spec["profileId"],
            "platform": spec["platform"],
            "model": spec["model"],
            "views": [
                {
                    "id": "front",
                    "label": "Front View",
                    "image": f"/chassis-assets/{self.name}/{svg_name}",
                    "width": WIDTH,
                    "height": HEIGHT,
                    "sourceWidth": WIDTH,
                    "sourceHeight": HEIGHT,
                    "sourceImage": spec["sourceProfile"],
                    "hotspots": self.hotspots,
                }
            ],
            "tree": self._tree(),
            "componentsById": self.components,
            "physicalIndexToComponentId": self.physical_index_map,
            "source": {
                "type": "hand-curated-static-profile",
                "profile": spec["sourceProfile"],
                "walk": spec["walk"],
            },
        }
        return profile, self._svg()


def main() -> None:
    for name, spec in VARIANTS.items():
        profile, svg = ProfileBuilder(name, spec).build()
        svg_name = f"{spec['model']}-Front.svg"
        for out_dir in (
            REPO_ROOT / "frontend" / "public" / "chassis-assets" / name,
            REPO_ROOT / "backend" / "app" / "data" / "chassis" / name,
        ):
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / svg_name).write_text(svg, encoding="utf-8")
            (out_dir / "normalized.json").write_text(
                json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        hotspots = len(profile["views"][0]["hotspots"])
        components = len(profile["componentsById"])
        print(f"{name}: {hotspots} hotspots, {components} components -> {svg_name}")


if __name__ == "__main__":
    main()
