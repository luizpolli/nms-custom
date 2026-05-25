#!/usr/bin/env python3
"""Normalize ENTITY-MIB snmpwalk files into chassis inventory summaries."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


ENT_PHYSICAL_COLUMNS = {
    2: "description",
    3: "vendorType",
    4: "containedPhysicalIndex",
    5: "physicalClass",
    6: "parentRelPos",
    7: "name",
    8: "hardwareVersion",
    9: "firmwareVersion",
    10: "softwareVersion",
    11: "serialNumber",
    12: "manufacturer",
    13: "modelName",
    14: "alias",
    15: "assetId",
    16: "isFRUable",
}

PHYSICAL_CLASS_LABELS = {
    1: "other",
    2: "unknown",
    3: "chassis",
    4: "backplane",
    5: "container",
    6: "powerSupply",
    7: "fan",
    8: "sensor",
    9: "module",
    10: "port",
    11: "stack",
    12: "cpu",
}

OID_RE = re.compile(r"(?:SNMPv2-SMI::)?mib-2\.47\.1\.1\.1\.1\.(?P<column>\d+)\.(?P<index>\d+)\s+=\s+(?P<type>[^:]+):?\s*(?P<value>.*)$")
MODEL_RE = re.compile(r"(NCS55A1|NCS560|NCS540)", re.IGNORECASE)
PORT_NAME_RE = re.compile(
    r"\b(?:FourHundredGigE|HundredGigE|FortyGigE|TwentyFiveGigE|TenGigE|GigabitEthernet|MgmtEth|Optics)\S+"
)


def clean_value(value: str) -> Any:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    if value == "":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def model_from_path(path: Path) -> str:
    match = MODEL_RE.search(path.name)
    if not match:
        return path.stem
    return match.group(1).upper()


def parse_ent_physical_walk(path: Path) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = collections.defaultdict(dict)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = OID_RE.match(line)
        if not match:
            continue
        column = int(match.group("column"))
        key = ENT_PHYSICAL_COLUMNS.get(column)
        if key is None:
            continue
        index = int(match.group("index"))
        rows[index]["physicalIndex"] = index
        rows[index][key] = clean_value(match.group("value"))

    return {index: rows[index] for index in sorted(rows)}


def component_type(row: dict[str, Any]) -> str:
    physical_class = row.get("physicalClass")
    if isinstance(physical_class, int):
        return PHYSICAL_CLASS_LABELS.get(physical_class, f"class-{physical_class}")
    return "unknown"


def chassis_component_id(index: int) -> str:
    return f"component-{index}"


def slot_key(row: dict[str, Any]) -> str | None:
    name = str(row.get("name") or "")
    description = str(row.get("description") or "")
    text = f"{name} {description}"

    port_match = PORT_NAME_RE.search(text)
    if port_match:
        return port_match.group(0)

    for pattern in [
        r"\b(?:QSFP28|QSFP|SFP) bay \d+\b",
        r"\bPower Module \d+\b",
        r"\bFan \d+\b",
        r"\b0/FT\d+\b",
        r"\b0/PM\d+\b",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)

    # Only treat route-processor or line-card names as slot keys when the
    # component itself is the slot/module, not every child under that slot.
    if re.fullmatch(r"0/RP\d+(?:/CPU\d+)?", name):
        return name
    if re.fullmatch(r"0/\d+", name):
        return name
    return None


def normalize_components(rows: dict[int, dict[str, Any]]) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {}
    physical_index_to_component_id: dict[str, str] = {}

    for index, row in rows.items():
        component_id = chassis_component_id(index)
        parent_index = row.get("containedPhysicalIndex")
        parent_id = chassis_component_id(parent_index) if isinstance(parent_index, int) and parent_index in rows else None
        display_name = row.get("name") or row.get("description") or f"Physical component {index}"
        normalized = {
            "id": component_id,
            "sourceId": index,
            "parentId": parent_id,
            "physicalIndex": index,
            "containedPhysicalIndex": parent_index,
            "name": display_name,
            "displayName": display_name,
            "description": row.get("description"),
            "type": component_type(row),
            "physicalClass": row.get("physicalClass"),
            "physicalClassLabel": component_type(row),
            "parentRelPos": row.get("parentRelPos"),
            "vendorType": row.get("vendorType"),
            "typeId": row.get("modelName"),
            "modelName": row.get("modelName"),
            "serialNumber": row.get("serialNumber"),
            "manufacturer": row.get("manufacturer"),
            "hardwareVersion": row.get("hardwareVersion"),
            "firmwareVersion": row.get("firmwareVersion"),
            "softwareVersion": row.get("softwareVersion"),
            "alias": row.get("alias"),
            "assetId": row.get("assetId"),
            "isFRUable": row.get("isFRUable"),
            "slotKey": slot_key(row),
            "ports": [],
            "childIds": [],
        }
        components[component_id] = {key: value for key, value in normalized.items() if value is not None}
        physical_index_to_component_id[str(index)] = component_id

    for component in components.values():
        parent_id = component.get("parentId")
        if parent_id and parent_id in components:
            components[parent_id].setdefault("childIds", []).append(component["id"])

    for component in components.values():
        component["childIds"] = sorted(component.get("childIds", []), key=lambda item: components[item]["physicalIndex"])

    return {
        "componentsById": dict(sorted(components.items(), key=lambda item: item[1]["physicalIndex"])),
        "physicalIndexToComponentId": physical_index_to_component_id,
    }


def build_tree_node(component_id: str, components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    component = components[component_id]
    return {
        "id": component_id,
        "label": component.get("displayName") or component.get("name") or component_id,
        "type": component.get("type", "unknown"),
        "physicalIndex": component.get("physicalIndex"),
        "componentId": component_id,
        "children": [build_tree_node(child_id, components) for child_id in component.get("childIds", [])],
    }


def root_component_ids(components: dict[str, dict[str, Any]]) -> list[str]:
    roots = [component["id"] for component in components.values() if not component.get("parentId")]
    chassis_roots = [component["id"] for component in components.values() if component.get("physicalClass") == 3]
    return chassis_roots or roots


def summarize_components(model: str, rows: dict[int, dict[str, Any]], components: dict[str, dict[str, Any]]) -> dict[str, Any]:
    class_counts = collections.Counter(component_type(row) for row in rows.values())
    fru_components = [
        c
        for c in components.values()
        if c.get("isFRUable") is True or c.get("type") in {"chassis", "container", "fan", "module", "powerSupply", "port"}
    ]
    port_components = [
        c
        for c in components.values()
        if c.get("type") == "port" or PORT_NAME_RE.search(str(c.get("name", ""))) or PORT_NAME_RE.search(str(c.get("description", "")))
    ]
    hotspot_types = {"container", "fan", "module", "powerSupply", "port"}
    hotspots = [c for c in fru_components if c.get("type") in hotspot_types and c.get("slotKey")]

    top_level = [
        {
            "physicalIndex": c.get("physicalIndex"),
            "name": c.get("name"),
            "description": c.get("description"),
            "type": c.get("type"),
            "children": len(c.get("childIds", [])),
        }
        for c in components.values()
        if not c.get("parentId")
    ]

    return {
        "model": model,
        "componentCount": len(rows),
        "classCounts": dict(sorted(class_counts.items())),
        "fruCandidateCount": len(fru_components),
        "portCandidateCount": len(port_components),
        "hotspotCandidateCount": len(hotspots),
        "topLevelComponents": top_level,
        "sampleFruCandidates": compact_components(fru_components[:30]),
        "samplePortCandidates": compact_components(port_components[:40]),
        "sampleHotspotCandidates": compact_components(hotspots[:40]),
    }


def compact_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ["physicalIndex", "containedPhysicalIndex", "type", "slotKey", "name", "description", "typeId", "isFRUable"]
    return [{key: component.get(key) for key in keys if component.get(key) is not None} for component in components]


def normalize_file(path: Path) -> dict[str, Any]:
    model = model_from_path(path)
    rows = parse_ent_physical_walk(path)
    normalized = normalize_components(rows)
    components = normalized["componentsById"]
    roots = root_component_ids(components)
    tree = [build_tree_node(component_id, components) for component_id in roots]
    summary = summarize_components(model, rows, components)
    return {
        "schemaVersion": "nms.entityMibWalk.v1",
        "model": model,
        "sourceFile": path.name,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        **normalized,
        "tree": tree,
        "summary": summary,
    }


def write_markdown(report: dict[str, Any], output_path: Path) -> None:
    lines = [
        "# SNMP Walk Chassis Summary",
        "",
        f"Generated at `{report['generatedAt']}` from sanitized ENTITY-MIB walks.",
        "",
    ]
    for item in report["devices"]:
        summary = item["summary"]
        lines.extend(
            [
                f"## {summary['model']}",
                "",
                f"- Components: {summary['componentCount']}",
                f"- FRU/hotspot candidates: {summary['fruCandidateCount']} / {summary['hotspotCandidateCount']}",
                f"- Port candidates: {summary['portCandidateCount']}",
                f"- ENTITY-MIB classes: `{json.dumps(summary['classCounts'], sort_keys=True)}`",
                "",
                "### Top Level",
                "",
            ]
        )
        for component in summary["topLevelComponents"]:
            lines.append(
                f"- `{component['physicalIndex']}` {component.get('type')}: "
                f"{component.get('name') or component.get('description')} "
                f"({component['children']} children)"
            )
        lines.extend(["", "### First Hotspot Candidates", ""])
        for component in summary["sampleHotspotCandidates"][:20]:
            lines.append(
                f"- `{component['physicalIndex']}` {component.get('type')} "
                f"`{component.get('slotKey')}`: {component.get('name') or component.get('description')}"
            )
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize sanitized entPhysical snmpwalk files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("docs/snmpwalks/sanitized"),
        help="Directory containing entPhysical*.walk files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/snmpwalks/normalized"),
        help="Directory where normalized JSON and markdown summaries are written.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    devices = []
    for path in sorted(args.input_dir.glob("entPhysical*.walk")):
        normalized = normalize_file(path)
        model = normalized["model"].lower()
        output_path = args.output_dir / f"{model}-entity-mib.json"
        output_path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        devices.append({"model": normalized["model"], "path": str(output_path), "summary": normalized["summary"]})

    report = {
        "schemaVersion": "nms.entityMibWalkSummary.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "inputDir": str(args.input_dir),
        "outputDir": str(args.output_dir),
        "devices": devices,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.output_dir / "summary.md")
    print(json.dumps({item["model"]: item["summary"]["classCounts"] for item in devices}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
