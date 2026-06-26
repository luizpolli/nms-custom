#!/usr/bin/env python3
"""Extract port-cage bounding boxes from an EPNM linecard / faceplate SVG.

This is the *authoritative* source for pixel-perfect port placement in the
Chassis View (see docs/CHASSIS_PIXEL_PERFECT_RUNBOOK.md).  The `pluggables.json`
"horizontal" coordinates live in a ~884-wide container space and sit ~12px to the
right of where the SVG actually draws the cages; the boxes this script reports are
in the SVG's own viewBox, so they line up 1:1 with the rendered faceplate.

It walks every <path>/<rect>, tracks the pen through absolute/relative path
commands (M/m L/l H/h V/v C/c S/s Q/q T/t A/a Z), and reports boxes whose size
matches a cage filter.  Cages cluster into rows by Y; the per-row X list is what
you feed into normalized.json as `bounds.x = OFFSET + cage.x`.

Usage:
    python3 scripts/extract_svg_cages.py <file.svg> [wmin wmax hmin hmax]

Defaults: w in [20,90], h in [25,50] (typical SFP/QSFP cage).  Example:
    python3 scripts/extract_svg_cages.py \\
        frontend/public/chassis-assets/asr920/modules/ASR-920-20SZ-M-Front_linecard.svg \\
        40 80 25 50
"""
import collections
import re
import sys


def path_bboxes(d: str):
    """Conservative bbox of one path's `d` (includes control points)."""
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|-?\d*\.?\d+(?:e-?\d+)?', d)
    i = 0
    cx = cy = sx = sy = 0.0
    cmd = None
    minx = miny = 1e18
    maxx = maxy = -1e18

    def upd(x, y):
        nonlocal minx, miny, maxx, maxy
        minx, miny, maxx, maxy = min(minx, x), min(miny, y), max(maxx, x), max(maxy, y)

    n = len(toks)
    while i < n:
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
        c = cmd
        try:
            if c in 'Mm':
                x, y = float(toks[i]), float(toks[i + 1]); i += 2
                if c == 'm':
                    x += cx; y += cy
                cx, cy = x, y; sx, sy = x, y; upd(cx, cy)
                cmd = 'l' if c == 'm' else 'L'
            elif c in 'Ll':
                x, y = float(toks[i]), float(toks[i + 1]); i += 2
                if c == 'l':
                    x += cx; y += cy
                cx, cy = x, y; upd(cx, cy)
            elif c in 'Hh':
                x = float(toks[i]); i += 1
                if c == 'h':
                    x += cx
                cx = x; upd(cx, cy)
            elif c in 'Vv':
                y = float(toks[i]); i += 1
                if c == 'v':
                    y += cy
                cy = y; upd(cx, cy)
            elif c in 'Cc':
                pts = [float(toks[i + k]) for k in range(6)]; i += 6
                if c == 'c':
                    pts = [pts[k] + (cx if k % 2 == 0 else cy) for k in range(6)]
                upd(pts[0], pts[1]); upd(pts[2], pts[3]); upd(pts[4], pts[5])
                cx, cy = pts[4], pts[5]
            elif c in 'Ss':
                pts = [float(toks[i + k]) for k in range(4)]; i += 4
                if c == 's':
                    pts = [pts[k] + (cx if k % 2 == 0 else cy) for k in range(4)]
                upd(pts[0], pts[1]); upd(pts[2], pts[3]); cx, cy = pts[2], pts[3]
            elif c in 'Qq':
                pts = [float(toks[i + k]) for k in range(4)]; i += 4
                if c == 'q':
                    pts = [pts[k] + (cx if k % 2 == 0 else cy) for k in range(4)]
                upd(pts[0], pts[1]); upd(pts[2], pts[3]); cx, cy = pts[2], pts[3]
            elif c in 'Tt':
                x, y = float(toks[i]), float(toks[i + 1]); i += 2
                if c == 't':
                    x += cx; y += cy
                cx, cy = x, y; upd(cx, cy)
            elif c in 'Aa':
                a = [float(toks[i + k]) for k in range(7)]; i += 7
                x, y = a[5], a[6]
                if c == 'a':
                    x += cx; y += cy
                upd(x, y); cx, cy = x, y
            elif c in 'Zz':
                cx, cy = sx, sy
            else:
                i += 1
        except (IndexError, ValueError):
            break
    if maxx < minx:
        return None
    return (minx, miny, maxx - minx, maxy - miny)


def rect_bboxes(svg: str):
    out = []
    for m in re.finditer(r'<rect\b[^>]*>', svg):
        s = m.group(0)

        def g(k):
            mm = re.search(r'\b%s="([\-\d.]+)"' % k, s)
            return float(mm.group(1)) if mm else None
        x, y, w, h = g('x'), g('y'), g('width'), g('height')
        if None not in (x, y, w, h):
            out.append((x, y, w, h))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    f = sys.argv[1]
    t = open(f, errors='ignore').read()
    vb = re.search(r'viewBox="([\d.\- ]+)"', t)
    print("viewBox:", vb.group(1) if vb else "?")

    boxes = rect_bboxes(t)
    boxes += [b for b in (path_bboxes(d) for d in re.findall(r'<path[^>]*\bd="([^"]+)"', t)) if b]

    wmin, wmax, hmin, hmax = [float(x) for x in (sys.argv[2:6] or [20, 90, 25, 50])]
    cages = [b for b in boxes if wmin <= b[2] <= wmax and hmin <= b[3] <= hmax]
    print(f"boxes={len(boxes)}  cage-filter w[{wmin},{wmax}] h[{hmin},{hmax}] -> {len(cages)}")
    sz = collections.Counter((round(b[2] / 5) * 5, round(b[3] / 5) * 5) for b in cages)
    print("size buckets (w,h)->n:", dict(sz.most_common(10)))

    rows = collections.defaultdict(list)
    for x, y, w, h in cages:
        rows[round(y / 10) * 10].append((round(x, 1), round(y, 1), round(w, 1), round(h, 1)))
    for y in sorted(rows):
        cells = sorted(rows[y])
        xs = [c[0] for c in cells]
        if len(xs) >= 1:
            pitch = round(sum(xs[k + 1] - xs[k] for k in range(len(xs) - 1)) / max(1, len(xs) - 1), 1)
            print(f"  row y~{y}: n={len(xs)} x0={xs[0]} xN={xs[-1]} pitch~{pitch}")
            print(f"    cells (x,y,w,h): {cells}")


if __name__ == "__main__":
    main()
