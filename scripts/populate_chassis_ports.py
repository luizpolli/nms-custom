#!/usr/bin/env python3
"""Populate chassis-view port hotspots from EPNM pluggables cage geometry.

A generated profile (generate_chassis_profile.py) only has empty slot bays.
This step assigns a real card to each line-card / RP slot, reads that card's
per-port cage rectangles from the family pluggables.json (EPNM ground truth),
scales them into the slot's bounds on the chassis, and emits one clickable port
hotspot per cage (plus child port components for the tree). Real port count and
layout — not fabricated.

Usage: python3 scripts/populate_chassis_ports.py [profileId ...]   (default: all)
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "frontend/public/chassis-assets"
DP = REPO / "docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile"

PLUG = {
    "ASR9K": DP / "ASR9K-IOSXR/pluggables/data/pluggables.json",
    "NCS55XX": DP / "NCS55XX_CE/pluggables/data/pluggables.json",
}

# profileId -> {plug, byLabel:{slotLabel:(cardPID, portPrefix)}}
# portPrefix MUST start with a token matched by ChassisView PORT_HOTSPOT_RE
# (QSFP|SFP|Gi|GE|Te|Hu|Fo|Fa|Eth|Mgmt).
# RP/RSP mgmt "ports" in pluggables use an inconsistent coordinate frame
# (e.g. A99-RP2 cage x=936 against a 144-wide frame), so we only populate the
# line-card slots — the actual data ports.
CONFIG = {
    "asr9901": {"plug": "ASR9K", "byLabel": {
        "Line Card Slot": ("ASR-9901-LC", "TenGigE")}},
    "asr9902": {"plug": "ASR9K", "byLabel": {
        "Line Card Slot": ("ASR-9902-LC", "TenGigE")}},
    "asr9903": {"plug": "ASR9K", "byLabel": {
        "Line Card Slot": ("ASR-9903-LC", "HundredGigE")}},
    "ncs5516": {"plug": "NCS55XX", "byLabel": {
        "Line Card Slot": ("NC55-36X100G", "HundredGigE")}},
    "ncs560-4": {"plug": "NCS55XX", "byLabel": {
        "Line Card Slot": ("A900-IMA8CS1Z-M", "TenGigE")}},
    "ncs560-enh": {"plug": "NCS55XX", "byLabel": {
        "Line Card Slot": ("A900-IMA8CS1Z-M", "TenGigE")}},
}

SID_RE = re.compile(r'"id"\s*:\s*"([^"]+)"\s*,\s*"nodeId"\s*:\s*"([^"]+)"')


def find_faceplate_svg(svg_id: str, orient: str) -> Path | None:
    """Locate a card faceplate SVG in any family's pluggables/images/<orient>."""
    for root in DP.glob(f"*/pluggables/images/{orient}"):
        f = root / svg_id
        if f.exists():
            return f
    return None


def module_block(text: str, pid: str) -> str | None:
    i = text.find(f'"{pid}": {{')
    if i < 0:
        i = text.find(f'"{pid}":{{')
    if i < 0:
        return None
    j = text.find("{", i)
    depth = 0
    for k in range(j, len(text)):
        c = text[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[j:k + 1]
    return None


def _brace(s: str, i: int) -> str:
    """Return the brace-balanced object starting at the `{` at index i."""
    depth = 0
    for k in range(i, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return s[i:k + 1]
    return s[i:]


def _num(blob: str, key: str) -> float | None:
    m = re.search(rf'"?{key}"?\s*:\s*([\d.]+)', blob)
    return float(m.group(1)) if m else None


def _rect(blob: str) -> dict | None:
    """Extract x/y/width/height from a sub-block, key order/quote-independent."""
    g = {k: _num(blob, k) for k in ("x", "y", "width", "height")}
    if any(v is None for v in g.values()):
        return None
    return {"x": g["x"], "y": g["y"], "w": g["width"], "h": g["height"]}


def card_cages(text: str, pid: str) -> dict | None:
    """Return {dims:{horizontal,vertical}, ports:[{horizontal,vertical}]}."""
    block = module_block(text, pid)
    if not block:
        return None
    svg_m = re.search(r'"?svgImageId"?\s*:\s*"([^"]+)"', block)
    svg_id = svg_m.group(1) if svg_m else None
    # Frame dims come from the module's `orientation` object (brace-matched),
    # NOT the flat top-level width/height (which can disagree with the cages).
    dims = {}
    om = re.search(r'"?orientation"?\s*:\s*\{', block)
    if om:
        ob = _brace(block, block.index("{", om.end() - 1))
        for name in ("horizontal", "vertical"):
            nm = re.search(rf'"?{name}"?\s*:\s*\{{', ob)
            if nm:
                sub = _brace(ob, ob.index("{", nm.end() - 1))
                w, h = _num(sub, "width"), _num(sub, "height")
                if w and h:
                    dims[name] = {"width": w, "height": h}
    matches = list(SID_RE.finditer(block))
    ports = []
    for idx, sm in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        tail = block[sm.end():end]
        rects = {}
        for name in ("horizontal", "vertical"):
            nm = re.search(rf'"?{name}"?\s*:\s*\{{', tail)
            if nm:
                rr = _rect(_brace(tail, tail.index("{", nm.end() - 1)))
                if rr:
                    rects[name] = rr
        if rects:
            ports.append(rects)
    if not ports:
        return None
    return {"dims": dims, "ports": ports, "svg": svg_id}


def scale_ports(card: dict, slot: dict) -> tuple[str | None, list[dict]]:
    """Map each card cage into the slot bounds. Returns (orientation_used, cages).

    Picks the card orientation matching the slot aspect so the faceplate art and
    the cages share one coordinate frame (no transpose needed for our wide slots).
    """
    sx, sy, sw, sh = slot["x"], slot["y"], slot["w"], slot["h"]
    slot_vert = sh > sw
    want = "vertical" if slot_vert else "horizontal"
    have = want if (want in card["dims"] and all(want in p for p in card["ports"])) else None
    if not have:
        have = "horizontal" if any("horizontal" in p for p in card["ports"]) else "vertical"
    dims = card["dims"].get(have)
    if not dims:
        return None, []
    cw, ch = dims["width"], dims["height"]
    transpose = (have == "horizontal") != (not slot_vert)  # card orient != slot orient
    out = []
    for p in card["ports"]:
        r = p.get(have)
        if not r:
            continue
        if not transpose:
            bx = sx + (r["x"] / cw) * sw
            by = sy + (r["y"] / ch) * sh
            bw = (r["w"] / cw) * sw
            bh = (r["h"] / ch) * sh
        else:
            # card's long (x/width) axis runs down the slot's long (height) axis
            by = sy + (r["x"] / cw) * sh
            bx = sx + (r["y"] / ch) * sw
            bh = (r["w"] / cw) * sh
            bw = (r["h"] / ch) * sw
        bw = max(bw, 4)
        bh = max(bh, 4)
        # safety clamp: keep every cage inside its slot
        bx = min(max(bx, sx), sx + sw - bw)
        by = min(max(by, sy), sy + sh - bh)
        out.append({"x": round(bx, 1), "y": round(by, 1),
                    "w": round(bw, 1), "h": round(bh, 1)})
    return have, out


def populate(profile_id: str) -> None:
    cfg = CONFIG[profile_id]
    text = PLUG[cfg["plug"]].read_text()
    path = ASSETS / profile_id / "normalized.json"
    model = json.loads(path.read_text())
    cards = {label: card_cages(text, pid)
             for label, (pid, _) in cfg["byLabel"].items()}

    pidx = 9000000
    total_ports = 0
    for view in model["views"]:
        new_hotspots = []
        for hs in view["hotspots"]:
            new_hotspots.append(hs)
            label = hs.get("label")
            if label not in cfg["byLabel"]:
                continue
            card = cards.get(label)
            if not card:
                continue
            card_pid, prefix = cfg["byLabel"][label]
            alias = hs.get("slotKey", "0")
            orient, cages = scale_ports(card, hs["bounds"])
            if not cages:
                continue
            # Composite the card faceplate art into the slot so the bay is not a
            # black hole; the cages were scaled in this same orientation's frame
            # so the ports land on the drawn cages.
            comp_id = hs.get("inventoryId")
            if card.get("svg"):
                src = find_faceplate_svg(card["svg"], orient or "horizontal")
                if src:
                    dst = ASSETS / profile_id / src.name
                    if not dst.exists():
                        dst.write_bytes(src.read_bytes())
                    hs["asset"] = {"image": f"/chassis-assets/{profile_id}/{src.name}",
                                   "typeId": card_pid}
            comp = model["componentsById"].get(comp_id)
            child_ids, comp_ports = [], []
            for i, b in enumerate(cages):
                pidx += 1
                pid_s = str(pidx)
                ifname = f"{prefix}0/{alias}/0/{i}"
                hid = f"hs-{profile_id}-{comp_id}-p{i}"
                pcid = f"comp-port-{pid_s}"
                new_hotspots.append({
                    "id": hid, "slotKey": ifname, "label": ifname,
                    "inventoryId": pcid, "physicalIndex": pidx, "empty": False,
                    "bounds": b,
                    "metadata": {"card": card_pid, "port": ifname},
                })
                model["componentsById"][pcid] = {
                    "id": pcid, "name": ifname, "displayName": ifname,
                    "type": "Port", "typeId": "SFP", "parentId": comp_id,
                    "ports": [], "childIds": [],
                }
                child_ids.append(pcid)
                comp_ports.append({"id": pid_s, "name": ifname, "portId": pidx})
                total_ports += 1
            if comp:
                comp["empty"] = False
                comp["name"] = card_pid
                comp["displayName"] = card_pid
                comp["typeId"] = card_pid
                comp["ports"] = comp_ports
                comp["childIds"] = child_ids
            # mark the slot hotspot as populated
            hs["empty"] = False
            hs["metadata"] = {**(hs.get("metadata") or {}), "card": card_pid}
        view["hotspots"] = new_hotspots
    path.write_text(json.dumps(model, indent=2))
    print(f"{profile_id}: +{total_ports} port hotspots "
          f"(cards: {', '.join(p for p, _ in cfg['byLabel'].values())})")


def main() -> None:
    ids = sys.argv[1:] or list(CONFIG)
    for pid in ids:
        if pid not in CONFIG:
            print(f"  ! no config for {pid}", file=sys.stderr)
            continue
        populate(pid)


if __name__ == "__main__":
    main()
