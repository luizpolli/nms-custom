#!/usr/bin/env python3
"""Generate an NMS chassis-view profile (normalized.json + SVG copy) from an EPNM
device-profile model dir.

The EPNM device profile gives the chassis SVG and per-slot anchors (x,y +
displayName + alias) but NOT slot box sizes, so we infer each slot's width and
height from the spacing to neighbouring slots. Output matches the
ChassisViewModel schema (frontend/src/pages/inventory/chassis/chassisTypes.ts):
slot-level hotspots over the chassis artwork (empty bays), componentsById + tree.

Populating slots with real modules/ports (via pluggables.json) is a follow-up;
this produces a structurally-correct, clickable chassis layout.

Usage:
  python3 scripts/generate_chassis_profile.py <epnm_model_dir> <profileId> "<Platform Name>"
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "frontend/public/chassis-assets"


def load_json5(path: Path) -> dict:
    t = path.read_text()
    t = re.sub(r"//[^\n]*", "", t)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    t = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)', r'\1"\2"\3', t)
    return json.loads(t)


def svg_viewbox(svg_path: Path) -> tuple[float, float]:
    t = svg_path.read_text()
    m = re.search(r'viewBox="[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)"', t)
    if m:
        return float(m.group(1)), float(m.group(2))
    w = re.search(r'width="([\d.]+)', t)
    h = re.search(r'height="([\d.]+)', t)
    return (float(w.group(1)) if w else 1000.0, float(h.group(1)) if h else 1000.0)


def type_for(display: str) -> str:
    d = (display or "").lower()
    if "line card" in d:
        return "Line Card"
    if "route processor" in d or "rsp" in d:
        return "Route Processor"
    if "power" in d:
        return "Power Module"
    if "fan" in d:
        return "Fan Tray"
    if "fabric" in d:
        return "Fabric Card"
    if "controller" in d:
        return "System Controller"
    return display or "Slot"


def _cluster(values: list[float], tol: float) -> list[float]:
    """Return cluster-center for each value (groups values within tol)."""
    order = sorted(set(round(v, 1) for v in values))
    groups, cur = [], []
    for v in order:
        if cur and v - cur[-1] > tol:
            groups.append(cur)
            cur = []
        cur.append(v)
    if cur:
        groups.append(cur)
    center = {}
    for g in groups:
        c = sum(g) / len(g)
        for v in g:
            center[v] = c
    return center


def infer_boxes(slots: list[dict], vw: float, vh: float) -> None:
    """Fill each slot's w/h from the gap to the next slot in its row/column.

    Slots are grouped into rows (shared y) and columns (shared x); within each
    group the box extends to the next slot's anchor (robust to uneven spacing),
    falling back to the chassis edge or the group's median gap.
    """
    row_tol, col_tol = vh * 0.035, vw * 0.02
    row_of = _cluster([s["sy"] for s in slots], row_tol)
    col_of = _cluster([s["sx"] for s in slots], col_tol)
    for s in slots:
        s["_row"] = row_of[round(s["sy"], 1)]
        s["_col"] = col_of[round(s["sx"], 1)]

    def gaps(group_key: str, axis: str) -> list[float]:
        out = []
        keys = sorted({s[group_key] for s in slots})
        for k in keys:
            members = sorted((s[axis] for s in slots if s[group_key] == k))
            out += [b - a for a, b in zip(members, members[1:])]
        return out

    median_w = (sorted(gaps("_row", "sx"))[len(gaps("_row", "sx")) // 2]
                if gaps("_row", "sx") else vw * 0.2)
    median_h = (sorted(gaps("_col", "sy"))[len(gaps("_col", "sy")) // 2]
                if gaps("_col", "sy") else vh * 0.12)

    for s in slots:
        # Only tile against slots of the SAME kind (a fabric card's width must
        # not be bounded by a neighbouring fan-tray anchor in the same row).
        row_mates = sorted((o["sx"] for o in slots
                            if o["display"] == s["display"] and o["_row"] == s["_row"] and o["sx"] > s["sx"] + 1))
        col_mates = sorted((o["sy"] for o in slots
                            if o["display"] == s["display"] and o["_col"] == s["_col"] and o["sy"] > s["sy"] + 1))
        w = (row_mates[0] - s["sx"]) if row_mates else min(median_w, vw - s["sx"] - vw * 0.02)
        h = (col_mates[0] - s["sy"]) if col_mates else median_h
        s["w"] = max(12.0, min(w * 0.94, vw))
        s["h"] = max(12.0, min(h * 0.94, vh))
    for s in slots:
        s.pop("_row", None)
        s.pop("_col", None)


def build_view(view: dict, model_dir: Path) -> tuple | None:
    containers = view.get("containers", {})
    container = next((c for c in containers.values()
                      if isinstance(c, dict) and c.get("svgImageId") and c.get("slots")), None)
    if not container:
        return None
    svg_id = container["svgImageId"]
    svg_path = model_dir / "images" / svg_id
    if not svg_path.exists():
        print(f"  ! SVG missing: {svg_id}", file=sys.stderr)
        return None
    vw, vh = svg_viewbox(svg_path)
    cw = float(container.get("width") or vw)
    ch = float(container.get("height") or vh)
    sx_scale, sy_scale = vw / cw, vh / ch

    raw = container["slots"]
    slots = []
    for key, sv in raw.items():
        if not isinstance(sv, dict):
            continue
        slots.append({
            "key": key,
            "alias": sv.get("alias"),
            "display": sv.get("displayName") or key,
            "filler": sv.get("fillerTypeId"),
            "sx": float(sv.get("x", 0)) * sx_scale,
            "sy": float(sv.get("y", 0)) * sy_scale,
        })
    infer_boxes(slots, vw, vh)

    view_id = view.get("id", "front")
    hotspots, components, children = [], {}, []
    for i, s in enumerate(slots):
        comp_id = f"comp-{view_id}-{i}"
        ctype = type_for(s["display"])
        hotspots.append({
            "id": f"hs-{view_id}-{i}",
            "slotKey": str(s["alias"] if s["alias"] is not None else s["key"]),
            "label": s["display"],
            "inventoryId": comp_id,
            "physicalIndex": None,
            "empty": True,
            "bounds": {"x": round(s["sx"], 1), "y": round(s["sy"], 1),
                       "w": round(s["w"], 1), "h": round(s["h"], 1)},
            "metadata": {"alias": s["alias"], "fillerTypeId": s["filler"],
                         "sourceName": s["display"]},
        })
        components[comp_id] = {
            "id": comp_id, "name": s["display"], "displayName": s["display"],
            "type": ctype, "typeId": None, "empty": True, "ports": [], "childIds": [],
        }
        children.append({"id": f"node-{view_id}-{i}", "label": s["display"],
                         "type": ctype, "componentId": comp_id, "children": []})

    view_obj = {
        "id": view_id,
        "label": view.get("displayName") or view_id.capitalize(),
        "image": f"/chassis-assets/{{PID}}/{svg_id}",
        "width": round(vw, 1),
        "height": round(vh, 1),
        "hotspots": hotspots,
    }
    return view_obj, children, components, svg_path


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    model_dir = Path(sys.argv[1]).resolve()
    pid = sys.argv[2]
    platform = sys.argv[3]
    data_files = list((model_dir / "data").glob("*.json"))
    if not data_files:
        print(f"No data json in {model_dir}/data", file=sys.stderr)
        sys.exit(1)
    profile = load_json5(data_files[0])

    out_dir = ASSETS / pid
    out_dir.mkdir(parents=True, exist_ok=True)

    # Front view only: slots there tile vertically so box sizes are reliable.
    # Rear views (single row of tall fabric cards) lack a bottom anchor, so
    # their heights can't be inferred from EPNM data — opt in with --all-views.
    all_views = "--all-views" in sys.argv
    profile_views = profile.get("views", [])
    if not all_views:
        front = [v for v in profile_views if v.get("id") == "front"] or profile_views[:1]
        profile_views = front

    views, components = [], {}
    root_id = "comp-chassis"
    root_children = []
    tree_children = []
    for v in profile_views:
        built = build_view(v, model_dir)
        if not built:
            continue
        view_obj, children, comps, svg_path = built
        view_obj["image"] = view_obj["image"].replace("{PID}", pid)
        (out_dir / svg_path.name).write_bytes(svg_path.read_bytes())
        views.append(view_obj)
        components.update(comps)
        for node in children:
            components[node["componentId"]]["parentId"] = root_id
            root_children.append(node["componentId"])
        if v.get("id", "front") == "front":
            tree_children = children

    components[root_id] = {
        "id": root_id, "name": platform, "displayName": platform,
        "type": "Chassis", "typeId": None, "ports": [],
        "childIds": root_children,
    }
    chassis_node = {"id": "node-chassis", "label": platform, "type": "Chassis",
                    "componentId": root_id, "children": tree_children}

    model = {
        "schemaVersion": "nms.chassisView.v1",
        "generatedAt": "1970-01-01T00:00:00Z",
        "deviceId": pid,
        "profileId": pid,
        "platform": platform,
        "views": views,
        "tree": [chassis_node],
        "componentsById": components,
        "physicalIndexToComponentId": {},
        "source": {"type": "epnm-deviceprofile", "profile": str(model_dir.name)},
    }
    (out_dir / "normalized.json").write_text(json.dumps(model, indent=2))
    print(f"wrote {out_dir}/normalized.json  ({len(views)} views, "
          f"{sum(len(v['hotspots']) for v in views)} hotspots)")
    for v in views:
        print(f"  view {v['id']}: {v['width']}x{v['height']} {len(v['hotspots'])} slots")


if __name__ == "__main__":
    main()
