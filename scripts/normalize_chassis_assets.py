#!/usr/bin/env python3
"""Normalize selected EPNM chassis assets into the NMS Chassis View schema."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tarfile
from pathlib import Path
from typing import Any


ASR903_PATHS = {
    "inventory": (
        "applications/storm/chassisview/v2/pidsupport/inventory/"
        "asr90xFamily/Cisco_ASR_903_Router/ASR-903_inventory.json"
    ),
    "model": "applications/storm/chassisview/v2/data/Cisco_ASR_903.json",
    "profile": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "asr901Family/Cisco_ASR_903_Router/data/Cisco_ASR_903_Router.json"
    ),
    "image": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "asr901Family/Cisco_ASR_903_Router/images/ASR-903-Front.svg"
    ),
}

ASR9006_PATHS = {
    "inventory": (
        "applications/storm/chassisview/v2/pidsupport/inventory/"
        "ASR9K-IOSXR/Cisco_ASR_9006_Router/ASR-9006-AC_inventory.json"
    ),
    "profile": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "ASR9K-IOSXR/Cisco_ASR_9006_Router/data/Cisco_ASR_9006_Router.json"
    ),
    "image": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "ASR9K-IOSXR/Cisco_ASR_9006_Router/images/ASR-9006-AC-Front.svg"
    ),
}

ASR903_OUTPUT_ASSET_PATH = "/chassis-assets/asr903/ASR-903-Front.svg"
ASR903_OUTPUT_ASSET_BASE = "/chassis-assets/asr903"
ASR903_PLUGGABLE_IMAGE_PREFIX = (
    "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
    "asr901Family/pluggables/images/horizontal"
)
ASR9006_OUTPUT_ASSET_PATH = "/chassis-assets/asr9006/ASR-9006-AC-Front.svg"
ASR9006_OUTPUT_ASSET_BASE = "/chassis-assets/asr9006"
ASR9006_PLUGGABLE_IMAGE_PREFIX = (
    "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
    "ASR9K-IOSXR/pluggables/images/horizontal"
)

ASR9010_PATHS = {
    "inventory": (
        "applications/storm/chassisview/v2/pidsupport/inventory/"
        "ASR9K-IOSXR/Cisco_ASR_9010_Router/chassis ASR-9010-AC_inventory.json"
    ),
    "profile": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "ASR9K-IOSXR/Cisco_ASR_9010_Router/data/Cisco_ASR_9010_Router.json"
    ),
    "image": (
        "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
        "ASR9K-IOSXR/Cisco_ASR_9010_Router/images/ASR-9010-AC-Front.svg"
    ),
}
ASR9010_OUTPUT_ASSET_PATH = "/chassis-assets/asr9010/ASR-9010-AC-Front.svg"
ASR9010_OUTPUT_ASSET_BASE = "/chassis-assets/asr9010"
ASR9010_PLUGGABLE_IMAGE_PREFIX = (
    "applications/storm/chassisview/com.cisco.prime.deviceprofile/"
    "ASR9K-IOSXR/pluggables/images/horizontal"
)


def find_member(archive: tarfile.TarFile, suffix: str) -> tarfile.TarInfo:
    matches = [member for member in archive.getmembers() if member.isfile() and member.name.endswith(suffix)]
    if not matches:
        raise FileNotFoundError(f"Could not find tar member ending with {suffix!r}")
    if len(matches) > 1:
        matches.sort(key=lambda member: member.name)
    return matches[0]


def read_json(archive: tarfile.TarFile, suffix: str) -> dict[str, Any]:
    member = find_member(archive, suffix)
    extracted = archive.extractfile(member)
    if extracted is None:
        raise FileNotFoundError(member.name)
    return json.load(extracted)


def read_text(archive: tarfile.TarFile, suffix: str) -> str:
    member = find_member(archive, suffix)
    extracted = archive.extractfile(member)
    if extracted is None:
        raise FileNotFoundError(member.name)
    return extracted.read().decode("utf-8", errors="replace")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.upper() == "N/A":
        return None
    return text or None


def component_id(raw_id: Any) -> str:
    return f"component-{raw_id}"


def list_entries(entry: Any) -> list[dict[str, Any]]:
    if not entry:
        return []
    if isinstance(entry, list):
        return [item for item in entry if isinstance(item, dict)]
    if isinstance(entry, dict):
        return [entry]
    return []


def extract_ports(node: dict[str, Any]) -> list[dict[str, Any]]:
    slots = node.get("slots")
    if not isinstance(slots, dict):
        return []

    ports: list[dict[str, Any]] = []
    for entry in list_entries(slots.get("entry")):
        value = entry.get("value")
        if not isinstance(value, dict) or "portId" not in value:
            continue
        ports.append(
            {
                "id": str(value["portId"]),
                "name": clean_text(value.get("name") or entry.get("key")),
                "portId": value.get("portId"),
            }
        )
    return ports


def normalize_component(node: dict[str, Any], parent_id: str | None) -> dict[str, Any]:
    raw_id = node.get("id")
    normalized: dict[str, Any] = {
        "id": component_id(raw_id),
        "sourceId": raw_id,
        "parentId": parent_id,
        "name": clean_text(node.get("name")) or f"Component {raw_id}",
        "displayName": clean_text(node.get("displayName") or node.get("name")) or f"Component {raw_id}",
        "description": clean_text(node.get("description")),
        "type": clean_text(node.get("type")) or "Equipment",
        "typeId": clean_text(node.get("typeId")),
        "physicalIndex": node.get("physicalIndex"),
        "containedPhysicalIndex": node.get("containedPhysicalIndex"),
        "operStatus": clean_text(node.get("operStatus")),
        "serviceState": node.get("serviceState"),
        "serialNumber": clean_text(node.get("serialNumber")),
        "hardwareVersion": clean_text(node.get("hardwareVersion")),
        "manufacturer": clean_text(node.get("manufacturer")),
        "isFRUable": node.get("isFRUable"),
        "ports": extract_ports(node),
        "childIds": [],
    }
    return {key: value for key, value in normalized.items() if value is not None}


def normalize_tree(
    node: dict[str, Any],
    parent_id: str | None,
    components: dict[str, dict[str, Any]],
    physical_index: dict[str, str],
) -> dict[str, Any]:
    component = normalize_component(node, parent_id)
    node_id = component["id"]
    components[node_id] = component

    physical = component.get("physicalIndex")
    if physical is not None:
        physical_index[str(physical)] = node_id

    children = [
        normalize_tree(child, node_id, components, physical_index)
        for child in node.get("containingList", []) or []
        if isinstance(child, dict)
    ]
    component["childIds"] = [child["id"] for child in children]

    tree_node: dict[str, Any] = {
        "id": node_id,
        "label": component["displayName"],
        "type": component["type"],
        "physicalIndex": component.get("physicalIndex"),
        "componentId": node_id,
        "children": children,
    }
    if component.get("typeId"):
        tree_node["typeId"] = component["typeId"]
    return tree_node


def parse_profile_metadata(profile_text: str) -> dict[str, Any]:
    width_match = re.search(r"\bwidth:\s*(\d+)", profile_text)
    height_match = re.search(r"\bheight:\s*(\d+)", profile_text)
    image_match = re.search(r'svgImageId:\s*"([^"]+)"', profile_text)

    slots: dict[str, dict[str, Any]] = {}
    slot_pattern = re.compile(
        r'"(?P<key>[^"]+)"\s*:\s*\{\s*'
        r"x:\s*(?P<x>\d+),\s*"
        r"y:\s*(?P<y>\d+),\s*"
        r"alias:\s*(?P<alias>\d+),\s*"
        r'fillerTypeId:\s*"(?P<filler>[^"]+)",\s*'
        r'displayName:\s*"(?P<display>[^"]+)"',
        re.MULTILINE,
    )
    for match in slot_pattern.finditer(profile_text):
        slots[match.group("key")] = {
            "x": int(match.group("x")),
            "y": int(match.group("y")),
            "alias": int(match.group("alias")),
            "fillerTypeId": match.group("filler"),
            "displayName": match.group("display"),
        }

    return {
        "width": int(width_match.group(1)) if width_match else None,
        "height": int(height_match.group(1)) if height_match else None,
        "image": image_match.group(1) if image_match else None,
        "slots": slots,
    }


def extract_object_block(text: str, object_key: str) -> str:
    match = re.search(rf'"{re.escape(object_key)}"\s*:\s*\{{', text)
    if not match:
        raise ValueError(f"Could not find profile object {object_key!r}")

    start = match.end() - 1
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError(f"Could not parse profile object {object_key!r}")


def parse_number_field(block: str, key: str) -> float | None:
    match = re.search(rf"\b{re.escape(key)}:\s*(?P<value>[-.\d]+)", block)
    return float(match.group("value")) if match else None


def parse_string_field(block: str, key: str) -> str | None:
    match = re.search(rf'\b{re.escape(key)}:\s*"(?P<value>[^"]+)"', block)
    return match.group("value") if match else None


def parse_slot_entries(block: str) -> dict[str, dict[str, Any]]:
    slots: dict[str, dict[str, Any]] = {}
    slot_pattern = re.compile(r'"(?P<key>[^"]+)"\s*:\s*\{(?P<body>[^{}]+?)\}', re.MULTILINE | re.DOTALL)
    for match in slot_pattern.finditer(block):
        body = match.group("body")
        x = parse_number_field(body, "x")
        y = parse_number_field(body, "y")
        alias = parse_number_field(body, "alias")
        display = parse_string_field(body, "displayName")
        if x is None or y is None or alias is None or display is None:
            continue
        slots[match.group("key")] = {
            "x": x,
            "y": y,
            "alias": int(alias),
            "fillerTypeId": parse_string_field(body, "fillerTypeId"),
            "displayName": display,
        }
    return slots


def parse_named_profile_metadata(profile_text: str, object_key: str) -> dict[str, Any]:
    block = extract_object_block(profile_text, object_key)
    width = parse_number_field(block, "width")
    height = parse_number_field(block, "height")
    return {
        "width": width,
        "height": height,
        "image": parse_string_field(block, "svgImageId"),
        "slots": parse_slot_entries(block),
    }


def parse_svg_viewbox(svg_text: str) -> dict[str, float] | None:
    match = re.search(r'viewBox="(?P<x>[-.\d]+)\s+(?P<y>[-.\d]+)\s+(?P<w>[-.\d]+)\s+(?P<h>[-.\d]+)"', svg_text)
    if not match:
        return None
    return {
        "x": float(match.group("x")),
        "y": float(match.group("y")),
        "w": float(match.group("w")),
        "h": float(match.group("h")),
    }


def hotspot_size(slot_key: str, display_name: str) -> dict[str, int]:
    normalized = f"{slot_key} {display_name}".lower()
    if "fan" in normalized:
        return {"w": 210, "h": 458}
    if "power" in normalized:
        return {"w": 390, "h": 126}
    if "route processor" in normalized or "slot_r" in normalized:
        return {"w": 820, "h": 145}
    return {"w": 552, "h": 72}


def asr9006_hotspot_size(slot_key: str, display_name: str) -> dict[str, float]:
    normalized = f"{slot_key} {display_name}".lower()
    if "fan" in normalized or "pan unit" in normalized:
        return {"w": 27, "h": 32}
    if "power" in normalized:
        return {"w": 50, "h": 16}
    return {"w": 138, "h": 16}


def normalize_slot_key(key: str) -> str:
    return key.replace("_", " ").replace("/", " ").lower()


def first_installed_child(
    component_id_value: str | None,
    components: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not component_id_value:
        return None

    component = components.get(component_id_value)
    if not component:
        return None
    if component.get("typeId"):
        return component

    for child_id in component.get("childIds", []):
        child = first_installed_child(child_id, components)
        if child and child.get("typeId"):
            return child
    return component


def slot_container_component_map(root_component: dict[str, Any]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for child_id in root_component.get("childIds", []):
        name = root_component.get("_components", {}).get(child_id, {}).get("name", "")
        if not name:
            continue
        slot_key = asr9006_slot_key_from_name(name)
        if slot_key:
            mapped[slot_key] = child_id
    return mapped


def asr9006_slot_key_from_name(name: str) -> str | None:
    lower = name.lower()
    match = re.search(r"slot 0/(\d+)$", lower)
    if match:
        return match.group(1)
    match = re.search(r"slot 0/(rsp\d+)$", lower)
    if match:
        return match.group(1).upper()
    match = re.search(r"slot 0/(ft\d+)$", lower)
    if match:
        return match.group(1).upper()
    match = re.search(r"slot 0/pm(\d+)$", lower)
    if match:
        return f"PS0/M{match.group(1)}"
    return None


def asr9010_slot_key_from_name(name: str) -> str | None:
    """Map a container component name to the ASR9010 profile slot key."""
    lower = name.lower()
    match = re.search(r"slot 0/(\d+)$", lower)
    if match:
        return match.group(1)
    match = re.search(r"slot 0/(rsp\d+)$", lower)
    if match:
        return match.group(1).upper()
    match = re.search(r"slot 0/(ft\d+)$", lower)
    if match:
        return match.group(1).upper()
    # PT0-PEM Bay N -> PS0/MN  ;  PT1-PEM Bay N -> PS1/MN
    match = re.search(r"pt(\d+)\s*-?\s*pem bay\s*(\d+)", lower)
    if match:
        return f"PS{match.group(1)}/M{match.group(2)}"
    match = re.search(r"slot 0/pm(\d+)$", lower)
    if match:
        # legacy single-PT representation
        return f"PS0/M{match.group(1)}"
    return None


def asr9010_hotspot_size(slot_key: str, display_name: str) -> dict[str, float]:
    """Approximate slot footprint in profile coord space (186 wide x 331 tall)."""
    normalized = f"{slot_key} {display_name}".lower()
    if "fan" in normalized:
        return {"w": 170, "h": 15}
    if "power" in normalized:
        return {"w": 46, "h": 20}
    # line card / route processor slots are vertical strips at the top half
    return {"w": 15, "h": 145}


def asset_type_for_profile(profile: str, type_id: str | None, filler_type_id: str | None) -> str | None:
    asset_type_id = type_id or filler_type_id
    if profile == "asr9006" and asset_type_id == "ASR-9006-FAN":
        return "ASR-9006-FAN-V2"
    if profile == "asr9006" and asset_type_id == "A9K-RSP-8G":
        return "A9K-RSP-4G"
    if profile == "asr9010" and asset_type_id in ("A9K-FAN", "ASR-9010-FAN"):
        return "ASR-9010-FAN"
    return asset_type_id


def build_hotspots(
    model: dict[str, Any],
    profile: dict[str, Any],
    components: dict[str, dict[str, Any]],
    physical_index: dict[str, str],
    coordinate_scale: dict[str, float],
) -> list[dict[str, Any]]:
    model_entries = list_entries(model["containers"].get("slots", {}).get("entry"))
    model_by_key = {normalize_slot_key(entry.get("key", "")): entry for entry in model_entries}

    hotspots: list[dict[str, Any]] = []
    for slot_key, slot in profile["slots"].items():
        model_entry = model_by_key.get(normalize_slot_key(slot_key))
        if not model_entry:
            model_entry = model_by_key.get(normalize_slot_key(slot_key.replace("/", " 0/")))

        model_value = model_entry.get("value", {}) if isinstance(model_entry, dict) else {}
        physical = model_value.get("physicalIndex")
        mapped_component_id = physical_index.get(str(physical)) if physical is not None else None
        installed_component = first_installed_child(mapped_component_id, components)
        inventory_id = installed_component["id"] if installed_component else mapped_component_id
        size = hotspot_size(slot_key, slot["displayName"])

        type_id = clean_text(installed_component.get("typeId")) if installed_component else clean_text(model_value.get("typeId"))
        asset_type_id = asset_type_for_profile("asr903", type_id, slot["fillerTypeId"])
        asset_image = f"{ASR903_OUTPUT_ASSET_BASE}/{asset_type_id}.svg" if asset_type_id else None
        x_scale = coordinate_scale["x"]
        y_scale = coordinate_scale["y"]

        hotspot = {
            "id": f"hotspot-{slot_key.replace('/', '-').replace('_', '-').replace(' ', '-')}",
            "slotKey": slot_key,
            "label": slot["displayName"],
            "inventoryId": inventory_id,
            "physicalIndex": physical,
            "empty": type_id is None,
            "bounds": {
                "x": round(slot["x"] * x_scale, 2),
                "y": round(slot["y"] * y_scale, 2),
                "w": round(size["w"] * x_scale, 2),
                "h": round(size["h"] * y_scale, 2),
            },
            "metadata": {
                "alias": slot["alias"],
                "fillerTypeId": slot["fillerTypeId"],
                "sourceName": clean_text(installed_component.get("displayName")) if installed_component else clean_text(model_value.get("name")),
                "sourceTypeId": type_id,
                "modelName": clean_text(model_value.get("name")),
                "modelTypeId": clean_text(model_value.get("typeId")),
            },
        }
        if asset_image:
            hotspot["asset"] = {
                "typeId": asset_type_id,
                "image": asset_image,
                "sourceImage": f"{ASR903_PLUGGABLE_IMAGE_PREFIX}/{asset_type_id}.svg",
            }

        hotspots.append(hotspot)

    return hotspots


def build_asr9006_hotspots(
    profile: dict[str, Any],
    components: dict[str, dict[str, Any]],
    coordinate_scale: dict[str, float],
) -> list[dict[str, Any]]:
    root_component = next((component for component in components.values() if component.get("parentId") is None), None)
    slot_to_component: dict[str, str] = {}
    if root_component:
        for child_id in root_component.get("childIds", []):
            child = components[child_id]
            slot_key = asr9006_slot_key_from_name(child.get("name", ""))
            if slot_key:
                slot_to_component[slot_key] = child_id

    hotspots: list[dict[str, Any]] = []
    for slot_key, slot in profile["slots"].items():
        mapped_component_id = slot_to_component.get(slot_key)
        installed_component = first_installed_child(mapped_component_id, components)
        inventory_id = installed_component["id"] if installed_component else mapped_component_id
        size = asr9006_hotspot_size(slot_key, slot["displayName"])
        type_id = clean_text(installed_component.get("typeId")) if installed_component else None
        asset_type_id = asset_type_for_profile("asr9006", type_id, slot.get("fillerTypeId"))
        asset_image = f"{ASR9006_OUTPUT_ASSET_BASE}/{asset_type_id}.svg" if asset_type_id else None
        x_scale = coordinate_scale["x"]
        y_scale = coordinate_scale["y"]

        hotspot = {
            "id": f"hotspot-{slot_key.replace('/', '-').replace('_', '-').replace(' ', '-')}",
            "slotKey": slot_key,
            "label": slot["displayName"],
            "inventoryId": inventory_id,
            "physicalIndex": installed_component.get("physicalIndex") if installed_component else None,
            "empty": type_id is None,
            "bounds": {
                "x": round(slot["x"] * x_scale, 2),
                "y": round(slot["y"] * y_scale, 2),
                "w": round(size["w"] * x_scale, 2),
                "h": round(size["h"] * y_scale, 2),
            },
            "metadata": {
                "alias": slot["alias"],
                "fillerTypeId": slot.get("fillerTypeId"),
                "sourceName": clean_text(installed_component.get("displayName")) if installed_component else None,
                "sourceTypeId": type_id,
            },
        }
        if asset_image:
            hotspot["asset"] = {
                "typeId": asset_type_id,
                "image": asset_image,
                "sourceImage": f"{ASR9006_PLUGGABLE_IMAGE_PREFIX}/{asset_type_id}.svg",
            }
        hotspots.append(hotspot)

    return hotspots


def build_asr9010_hotspots(
    profile: dict[str, Any],
    components: dict[str, dict[str, Any]],
    coordinate_scale: dict[str, float],
) -> list[dict[str, Any]]:
    """Build slot hotspots for ASR9010 using the profile slot map and live inventory."""
    root_component = next((component for component in components.values() if component.get("parentId") is None), None)
    slot_to_component: dict[str, str] = {}

    def collect_slots(component_id: str | None) -> None:
        if not component_id:
            return
        component = components.get(component_id)
        if not component:
            return
        slot_key = asr9010_slot_key_from_name(component.get("name", ""))
        if slot_key:
            slot_to_component.setdefault(slot_key, component_id)
        for child_id in component.get("childIds", []) or []:
            collect_slots(child_id)

    if root_component:
        collect_slots(root_component["id"])

    hotspots: list[dict[str, Any]] = []
    for slot_key, slot in profile["slots"].items():
        mapped_component_id = slot_to_component.get(slot_key)
        installed_component = first_installed_child(mapped_component_id, components)
        inventory_id = installed_component["id"] if installed_component else mapped_component_id
        size = asr9010_hotspot_size(slot_key, slot["displayName"])
        type_id = clean_text(installed_component.get("typeId")) if installed_component else None
        asset_type_id = asset_type_for_profile("asr9010", type_id, slot.get("fillerTypeId"))
        asset_image = f"{ASR9010_OUTPUT_ASSET_BASE}/{asset_type_id}.svg" if asset_type_id else None
        x_scale = coordinate_scale["x"]
        y_scale = coordinate_scale["y"]

        hotspot = {
            "id": f"hotspot-{slot_key.replace('/', '-').replace('_', '-').replace(' ', '-')}",
            "slotKey": slot_key,
            "label": slot["displayName"],
            "inventoryId": inventory_id,
            "physicalIndex": installed_component.get("physicalIndex") if installed_component else None,
            "empty": type_id is None,
            "bounds": {
                "x": round(slot["x"] * x_scale, 2),
                "y": round(slot["y"] * y_scale, 2),
                "w": round(size["w"] * x_scale, 2),
                "h": round(size["h"] * y_scale, 2),
            },
            "metadata": {
                "alias": slot["alias"],
                "fillerTypeId": slot.get("fillerTypeId"),
                "sourceName": clean_text(installed_component.get("displayName")) if installed_component else None,
                "sourceTypeId": type_id,
            },
        }
        if asset_image:
            hotspot["asset"] = {
                "typeId": asset_type_id,
                "image": asset_image,
                "sourceImage": f"{ASR9010_PLUGGABLE_IMAGE_PREFIX}/{asset_type_id}.svg",
            }
        hotspots.append(hotspot)

    return hotspots


def asset_type_ids(normalized: dict[str, Any]) -> list[str]:
    ids: set[str] = set()
    for view in normalized["views"]:
        for hotspot in view["hotspots"]:
            asset = hotspot.get("asset")
            if isinstance(asset, dict) and asset.get("typeId"):
                ids.add(str(asset["typeId"]))
    return sorted(ids)


def extract_assets(
    tarball: Path,
    output_dir: Path,
    normalized: dict[str, Any],
    chassis_image: str,
    chassis_filename: str,
    pluggable_prefix: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as archive:
        chassis_svg = read_text(archive, chassis_image)
        (output_dir / chassis_filename).write_text(chassis_svg, encoding="utf-8")

        for type_id in asset_type_ids(normalized):
            source = f"{pluggable_prefix}/{type_id}.svg"
            try:
                svg = read_text(archive, source)
            except FileNotFoundError:
                print(f"warning=missing_asset typeId={type_id} source={source}")
                continue
            (output_dir / f"{type_id}.svg").write_text(svg, encoding="utf-8")


def normalize_asr903(tarball: Path) -> dict[str, Any]:
    with tarfile.open(tarball, "r:gz") as archive:
        inventory = read_json(archive, ASR903_PATHS["inventory"])
        model = read_json(archive, ASR903_PATHS["model"])
        profile_text = read_text(archive, ASR903_PATHS["profile"])
        chassis_svg = read_text(archive, ASR903_PATHS["image"])

    components: dict[str, dict[str, Any]] = {}
    physical_index: dict[str, str] = {}
    root = inventory["containers"]
    tree = [normalize_tree(root, None, components, physical_index)]
    profile = parse_profile_metadata(profile_text)
    viewbox = parse_svg_viewbox(chassis_svg)
    image_width = viewbox["w"] if viewbox else profile["width"]
    image_height = viewbox["h"] if viewbox else profile["height"]
    coordinate_scale = {
        "x": image_width / profile["width"] if profile["width"] else 1,
        "y": image_height / profile["height"] if profile["height"] else 1,
    }
    hotspots = build_hotspots(model, profile, components, physical_index, coordinate_scale)

    return {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "package": str(tarball),
            "inventory": ASR903_PATHS["inventory"],
            "model": ASR903_PATHS["model"],
            "profile": ASR903_PATHS["profile"],
            "image": ASR903_PATHS["image"],
        },
        "deviceId": "sample-asr903",
        "profileId": "Cisco_ASR_903_Router",
        "platform": "Cisco ASR 903 Router",
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": ASR903_OUTPUT_ASSET_PATH,
                "sourceImage": ASR903_PATHS["image"],
                "width": image_width,
                "height": image_height,
                "sourceWidth": profile["width"],
                "sourceHeight": profile["height"],
                "hotspots": hotspots,
            }
        ],
        "tree": tree,
        "componentsById": components,
        "physicalIndexToComponentId": physical_index,
    }


def normalize_asr9006(tarball: Path) -> dict[str, Any]:
    with tarfile.open(tarball, "r:gz") as archive:
        inventory = read_json(archive, ASR9006_PATHS["inventory"])
        profile_text = read_text(archive, ASR9006_PATHS["profile"])
        chassis_svg = read_text(archive, ASR9006_PATHS["image"])

    components: dict[str, dict[str, Any]] = {}
    physical_index: dict[str, str] = {}
    root = inventory["containers"]
    tree = [normalize_tree(root, None, components, physical_index)]
    profile = parse_named_profile_metadata(profile_text, "ASR9006-AC")
    viewbox = parse_svg_viewbox(chassis_svg)
    image_width = viewbox["w"] if viewbox else profile["width"]
    image_height = viewbox["h"] if viewbox else profile["height"]
    coordinate_scale = {
        "x": image_width / profile["width"] if profile["width"] else 1,
        "y": image_height / profile["height"] if profile["height"] else 1,
    }
    hotspots = build_asr9006_hotspots(profile, components, coordinate_scale)

    return {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "package": str(tarball),
            "inventory": ASR9006_PATHS["inventory"],
            "profile": ASR9006_PATHS["profile"],
            "image": ASR9006_PATHS["image"],
        },
        "deviceId": "sample-asr9006",
        "profileId": "Cisco_ASR_9006_Router",
        "platform": "Cisco ASR 9006 Router",
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": ASR9006_OUTPUT_ASSET_PATH,
                "sourceImage": ASR9006_PATHS["image"],
                "width": image_width,
                "height": image_height,
                "sourceWidth": profile["width"],
                "sourceHeight": profile["height"],
                "hotspots": hotspots,
            }
        ],
        "tree": tree,
        "componentsById": components,
        "physicalIndexToComponentId": physical_index,
    }


def normalize_asr9010(tarball: Path) -> dict[str, Any]:
    with tarfile.open(tarball, "r:gz") as archive:
        inventory = read_json(archive, ASR9010_PATHS["inventory"])
        profile_text = read_text(archive, ASR9010_PATHS["profile"])
        chassis_svg = read_text(archive, ASR9010_PATHS["image"])

    components: dict[str, dict[str, Any]] = {}
    physical_index: dict[str, str] = {}
    root = inventory["containers"]
    tree = [normalize_tree(root, None, components, physical_index)]
    profile = parse_named_profile_metadata(profile_text, "ASR-9010")
    viewbox = parse_svg_viewbox(chassis_svg)
    image_width = viewbox["w"] if viewbox else profile["width"]
    image_height = viewbox["h"] if viewbox else profile["height"]
    coordinate_scale = {
        "x": image_width / profile["width"] if profile["width"] else 1,
        "y": image_height / profile["height"] if profile["height"] else 1,
    }
    hotspots = build_asr9010_hotspots(profile, components, coordinate_scale)

    return {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "package": str(tarball),
            "inventory": ASR9010_PATHS["inventory"],
            "profile": ASR9010_PATHS["profile"],
            "image": ASR9010_PATHS["image"],
        },
        "deviceId": "sample-asr9010",
        "profileId": "Cisco_ASR_9010_Router",
        "platform": "Cisco ASR 9010 Router",
        "views": [
            {
                "id": "front",
                "label": "Front View",
                "image": ASR9010_OUTPUT_ASSET_PATH,
                "sourceImage": ASR9010_PATHS["image"],
                "width": image_width,
                "height": image_height,
                "sourceWidth": profile["width"],
                "sourceHeight": profile["height"],
                "hotspots": hotspots,
            }
        ],
        "tree": tree,
        "componentsById": components,
        "physicalIndexToComponentId": physical_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize selected chassis assets for frontend/API use.")
    parser.add_argument("tarball", type=Path)
    parser.add_argument("--profile", choices=["asr903", "asr9006", "asr9010"], default="asr903")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--asset-output-dir", type=Path)
    args = parser.parse_args()

    if args.profile == "asr903":
        normalized = normalize_asr903(args.tarball)
        chassis_image = ASR903_PATHS["image"]
        chassis_filename = "ASR-903-Front.svg"
        pluggable_prefix = ASR903_PLUGGABLE_IMAGE_PREFIX
    elif args.profile == "asr9006":
        normalized = normalize_asr9006(args.tarball)
        chassis_image = ASR9006_PATHS["image"]
        chassis_filename = "ASR-9006-AC-Front.svg"
        pluggable_prefix = ASR9006_PLUGGABLE_IMAGE_PREFIX
    else:
        normalized = normalize_asr9010(args.tarball)
        chassis_image = ASR9010_PATHS["image"]
        chassis_filename = "ASR-9010-AC-Front.svg"
        pluggable_prefix = ASR9010_PLUGGABLE_IMAGE_PREFIX

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, indent=2, sort_keys=True), encoding="utf-8")
    if args.asset_output_dir:
        extract_assets(args.tarball, args.asset_output_dir, normalized, chassis_image, chassis_filename, pluggable_prefix)

    component_count = len(normalized["componentsById"])
    hotspot_count = len(normalized["views"][0]["hotspots"])
    mapped_hotspots = sum(1 for hotspot in normalized["views"][0]["hotspots"] if hotspot["inventoryId"])
    asset_count = len(asset_type_ids(normalized))
    print(f"profile={normalized['profileId']}")
    print(f"components={component_count}")
    print(f"hotspots={hotspot_count}")
    print(f"mapped_hotspots={mapped_hotspots}")
    print(f"assets={asset_count}")


if __name__ == "__main__":
    main()
