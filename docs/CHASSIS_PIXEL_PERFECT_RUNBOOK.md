# Chassis View — Pixel-Perfect Linecard / Port Mapping Runbook

Reference implementation: **ASR-920-20SZ-M** (`frontend/public/chassis-assets/asr920/`).
Follow these steps to bring any other model to the same fidelity (base chassis +
linecards + covers + port cages aligned 1:1, live up/down/admin-down status, full
inventory mapping, View Card replication).

---

## 0. What "done" looks like
- Base chassis SVG, linecard/faceplate SVGs and port connector SVGs stack in the
  right order and line up pixel-perfect.
- Every port cage carries a live status icon (up / down / admin-down).
- `N/N mapped hotspots` (every hotspot resolves to an inventory component).
- Selected Component, Port Inventory and the View Card all show the same ports.
- `cd frontend && npx tsc --noEmit` clean; overlay snapshot test green.

---

## 1. Ground-truth sources (EPNM device-profile export)
Under `docs/chassisview_figures/chassisview/com.cisco.prime.deviceprofile/<family>/`:

| File | Use |
|------|-----|
| `<Model>/data/*.json` (JSON5) | slot anchors → `displayName`, `fillerTypeId`, container `width`/`height` for PSU/RP/fan placement |
| `pluggables/data/pluggables.json` | per-port cage coords — module `<MODEL>_subslot/0`, `slots[].origin.horizontal`. **Parsing caution:** mixed quoted/unquoted keys + nested `original`/`horizontal` blocks; brace-match the module block that contains `"slots"`, then each slot's `"horizontal"` block, with a quote-tolerant number regex |
| `pluggables/images/horizontal/<Model>-Front_linecard.svg` | the real SFP line-card faceplate (its `viewBox` is the cage coordinate space) |
| `pluggables/images/horizontal/<Model>_slot_R0.svg` | RP / MGMT faceplate (RJ45 + USB) |
| `pluggables/images/horizontal/*PowerSupply*` , `modules/*PWR*` | PSU faceplates / fillers |

Copy the SVGs you need into `frontend/public/chassis-assets/<profile>/modules/`.

## 2. ⭐ KEY LESSON — extract cages from the SVG, not from pluggables.json
`pluggables.json` "horizontal" coords are authored in a ~884-wide **container**
space and sit **~12px to the right** of where the linecard SVG actually draws the
cages (the SVG `viewBox` is e.g. 856 wide). Using them directly makes ports drift
right, worse toward the right edge. **Always re-extract the real cage boxes from
the SVG:**

```bash
python3 scripts/extract_svg_cages.py \
  frontend/public/chassis-assets/asr920/modules/ASR-920-20SZ-M-Front_linecard.svg 40 80 25 50
# viewBox: 0 0 856 165 ; 28 cages of 54.4x34.9
# top row y~39.6: x = 18,73,129,186,241,297 | 380,436,491,548,604,659 | 741,796
# bottom row y~95.5: same X columns
```
Those `(x, y, w, h)` in the SVG's own viewBox are the truth. The X-gaps reveal the
physical port groups (here: 6 | 6 | 2 with the SFP+ uplinks in the separated right
group). Map ports column-by-column; on Cisco SFP faceplates port 0 is bottom-left,
port 1 top-left, port 2 bottom of the next column, etc.

## 3. normalized.json structure
`{ views:[{image,width,height,hotspots:[…]}], componentsById:{…}, tree:[…] }`

**Hotspot bounds are in the base chassis SVG `viewBox` space.** Pick `OFFSET` =
the linecard's left edge in that space (ASR920: `OFFSET = 614`).

- **Linecard background** (decorative): `metadata.kind:'linecard'`, `asset.image` =
  linecard SVG, `bounds {x:OFFSET, y:0, w:<viewBoxW>, h:<viewBoxH>}` (native 1:1 so
  the art maps 1:1 to the cage coords). Give it an `inventoryId` (chassis or the
  line-card module) so it counts as mapped. `ChassisCanvas` skips its clickable
  button (`metadata.kind==='linecard'`) so it never shows a selection box.
- **PSU / RP / fan faceplates**: `asset.image` = the real SVG, `bounds` from the
  EPNM slot anchors. **Split the RP**: one faceplate hotspot (the module, *no*
  port status) plus a small port hotspot sized to the **RJ45 jack** so the status
  icon lands on the jack, not the USB block. (Extract the jack box from
  `*_slot_R0.svg` the same way; ASR920 MgmtEth = jack `{x:555,y:29,w:48,h:37}`.)
- **Ports**: one hotspot per port, `bounds {x:OFFSET+cage.x, y:cage.y, w:cage.w,
  h:cage.h}` using the **SVG-extracted** cage coords, `asset` = `SFP.svg` /
  `QSFP.svg` connector, `inventoryId` = the port component.
- **componentsById**: each port component needs `operStatus` (drives the icon) and
  a `ports[]` entry (so it shows in the Port Inventory table).

**Layer order (back → front):** base chassis SVG → linecard / faceplate SVGs →
port connector SVGs → status icons (always rendered last/on top). In
`ChassisCanvas` this is array order for the `SlotAsset` images, so the linecard
hotspot must come **first** in `hotspots[]` and the port hotspots after it.

## 4. Status nomenclature
`PortStatus = 'up' | 'down' | 'admin-down'` from `classifyPortStatus(admin, oper)`.
It drives the chassis icons, the `PortStatusBadge` in Selected Component, the Port
Inventory `State` column, the legend counts and the View Card. Icons live in
`frontend/public/chassis-icons/{up,down,fi-admindown}.svg`.

## 5. Port admin toggle (demo simulate / live command)
`ChassisView` holds `adminOverrides`; `effectivePortStatusByComponentId` merges
base status + synthetic-by-hotspot + overrides and is fed to the canvas, panels and
legend. **Demo / static profile** → the toggle flips state locally (everything
updates live). **Live device** → it emits `interface X / shutdown|no shutdown` to
`/commands`. The toggle button lives only in the Port Inventory `Admin` column.

## 6. View Card replication
`buildZoomCard` emits per-port relative bounds —
`port.bounds = (hotspot.bounds − slot.bounds) / slot.bounds` — plus `aspect`
(`slot.w/slot.h`). `CardZoomModal` renders ports **absolutely** at those fractions
over the faceplate when bounds are present (even-grid fallback otherwise). No extra
data work needed once §3 is correct.

## 7. Verify (per model)
1. `cd frontend && npx tsc --noEmit` — **run from `frontend/`** (vitest/tsc config +
   happy-dom live there; from the repo root you get a false `document is not
   defined`).
2. Live preview, demo mode. **Full page reload** after editing `normalized.json` —
   HMR keeps the old JSON in memory; only a reload refetches it.
3. Numeric alignment check in the page (preview_eval): linecard `<img>` rect vs
   `OFFSET`; each port-button center (in viewBox units) vs `OFFSET + cage.x`.
4. `npx vitest run src/pages/inventory/chassis/overlaySnapshots.test.ts`; when the
   data legitimately changed, refresh with `-u`.

## 8. Per-model checklist
- [ ] Copy linecard + `slot_R0` + PSU/fan SVGs into `chassis-assets/<profile>/modules/`.
- [ ] `scripts/extract_svg_cages.py <linecard.svg>` → real cage coords + groups.
- [ ] Set `OFFSET` = linecard left edge in the base chassis viewBox.
- [ ] Build `normalized.json`: linecard bg (`kind:'linecard'`) → faceplates (RP split) → ports (real cage bounds + connector asset).
- [ ] Fill `componentsById` `operStatus` + `ports[]` for every port.
- [ ] Verify alignment (live + numeric); refresh overlay snapshot.
- [ ] Register the profile in `InventoryPage` `exampleChassisProfiles`.

---

### ASR-920-20SZ-M worked example (commits)
`a6044af` linecard 1:1 background · `a5b7d7d` SFP connectors in front ·
`b8eb34c` ports aligned to real SVG cages · `05b40d6` MgmtEth status on the RJ45 ·
`b13ca8a` decorative linecard (no selection box) · `cbf6884` admin toggle +
Up/Down/Admin-down nomenclature · `a9b414f` View Card replicates the mapped linecard.
