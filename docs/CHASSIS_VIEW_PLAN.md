# Chassis View v1.1 Implementation Plan

## Source Package

Kapy added the EPNM figures package. It now lives at:

- `.local/chassis-assets/figures.tar.gz`

The `.local/` directory is intentionally ignored by git so the raw 84 MB package stays in the project workspace without being committed.

Initial inspection:

- Size: 84 MB.
- Tar entries: 6,373 total entries.
- Files: 4,991.
- JSON files: 820.
- Chassis-related images: about 3,572 image files.
- EPNM-style chassis app code under:
  - `applications/storm/chassisview/v2/`
  - `applications/storm/chassisview/com.cisco.prime.deviceprofile/`
  - `applications/storm/chassisview/com.cisco.nms.chassis.nms-chassis-resource-rack/`
- Useful data exists in JSON, not just static images.

Important examples found:

- Generic chassis data:
  - `v2/data/Cisco_ASR_903.json`
  - `v2/data/Cisco_ASR_9904.json`
  - `v2/data/Cisco_ASR_9912.json`
  - `v2/data/Cisco_NCS_4016.json`
- Discovered inventory examples:
  - `v2/pidsupport/inventory/asr90xFamily/Cisco_ASR_903_Router/ASR-903_inventory.json`
  - `v2/pidsupport/inventory/asr90xFamily/Cisco_ASR_903_Router/ASR-903_chassisdata.json`
- Device profile examples:
  - `com.cisco.prime.deviceprofile/asr901Family/Cisco_ASR_903_Router/data/Cisco_ASR_903_Router.json`
  - `com.cisco.prime.deviceprofile/ASR9K-64CE/Cisco_ASR_9906_Router/data/Cisco_ASR_9906_Router.json`
  - `com.cisco.prime.deviceprofile/NCS540L_CE/...`
- Pluggable/profile mapping:
  - `v2/pidsupport/inventory/pidrelations.json`
  - `*/pluggables/data/pluggables.json`

Phase 1 audit output:

- Script: `scripts/audit_chassis_assets.py`
- Report: `docs/CHASSIS_ASSET_AUDIT.md`
- Local JSON report: `.local/chassis-assets/audit.json`

Phase 1 normalization output:

- Script: `scripts/normalize_chassis_assets.py`
- Frontend sample data: `frontend/public/chassis-assets/asr903/normalized.json`
- Curated ASR 903 front image: `frontend/public/chassis-assets/asr903/ASR-903-Front.svg`
- Frontend model types: `frontend/src/pages/inventory/chassis/chassisTypes.ts`

Current ASR 903 normalized sample:

- Components: 56 discovered inventory nodes.
- Views: 1 front view.
- Hotspots: 11 slot-level visual targets.
- Mapped hotspots: 11/11 mapped to real inventory components by physical index.
- Asset overlays: 9 installed/filler SVG types extracted for the ASR 903 sample.
- Geometry: profile coordinates are scaled to the real SVG `viewBox` so overlays align with the rendered chassis.
- Tree root: `Chassis`.
- First-level children include RSP slots, IM subslots, fan tray bay, and power supply bays.

## What Chassis View Should Be

The current mock is useful as a first visual pass, but it has fake controls and hardcoded visual-only pieces. The target behavior should be inventory-driven:

- Show the discovered equipment inventory as a tree.
- Show mapped ports under the selected module, including ports discovered through child transceiver nodes.
- Bind selected ports to persisted managed interfaces when the view is opened for a live device.
- Selecting a tree item highlights the matching physical element in the chassis figure.
- Selecting a chassis element highlights/selects the matching tree item.
- The detail panel shows real inventory attributes and selectable managed ports for that selected element.
- Actions should exist only when backed by real NMS behavior or a clear future hook.

## Functional Scope

Phase 1 should focus on read-only visual inventory:

- Device chassis figure.
- Front/rear toggle if the profile supports both.
- Discovered elements tree.
- Selection sync: tree to figure and figure to tree.
- Highlight overlay for chassis, slot, module, PSU, fan, port, and transceiver.
- Details panel with:
  - name
  - type
  - PID/typeId
  - serial
  - oper status
  - service state
  - physical index
  - parent/contained relationship
  - mapped ports/interfaces when present

Defer until data/actions exist:

- Launch Configuration.
- Sync Inventory.
- Alarms action.
- Interface action.
- Any toolbar button that does not perform a real operation.

## Proposed Architecture

### Backend

Add a normalized chassis inventory API instead of making the frontend understand raw EPNM JSON.

Suggested endpoints:

- `GET /devices/{device_id}/chassis`
  - returns selected profile, front/rear images, tree, components, and view metadata.
- `GET /devices/{device_id}/chassis/components/{component_id}`
  - returns detail for a single component.

Suggested normalized schema:

```json
{
  "deviceId": "uuid",
  "profileId": "Cisco_ASR_903_Router",
  "platform": "ASR 903",
  "views": [
    {
      "id": "front",
      "image": "/assets/chassis/asr901Family/Cisco_ASR_903_Router/images/front.svg",
      "width": 1200,
      "height": 320,
      "hotspots": [
        {
          "id": "module-r0",
          "inventoryId": "53689847",
          "physicalIndex": 100,
          "label": "module R0",
          "bounds": { "x": 120, "y": 42, "w": 280, "h": 80 }
        }
      ]
    }
  ],
  "tree": [
    {
      "id": "chassis-1",
      "label": "Chassis",
      "type": "Chassis",
      "children": []
    }
  ],
  "componentsById": {}
}
```

### Frontend

Create a dedicated chassis feature instead of keeping it inside `InventoryPage.tsx`.

Suggested files:

- `frontend/src/pages/inventory/chassis/ChassisView.tsx`
- `frontend/src/pages/inventory/chassis/DiscoveredElementsTree.tsx`
- `frontend/src/pages/inventory/chassis/ChassisCanvas.tsx`
- `frontend/src/pages/inventory/chassis/ComponentDetailsPanel.tsx`
- `frontend/src/pages/inventory/chassis/chassisTypes.ts`

The `ChassisCanvas` should render:

- base SVG/image for the equipment profile
- transparent clickable hotspot overlays
- selected hotspot outline/glow
- severity/status markers when available
- fit-to-view and zoom controls once the static selection flow is stable

### Asset Handling

Do not extract the full `figures.tar.gz` into the frontend blindly.

Recommended process:

1. Create a curated asset folder:
   - `frontend/public/chassis-assets/`
2. Start with one or two profiles:
   - ASR 903
   - ASR 9906 or ASR 9006
3. Copy only the needed profile JSON, base SVGs, pluggables, and icons.
4. Add a manifest:
   - `frontend/public/chassis-assets/manifest.json`
5. Keep raw EPNM package outside git until we know what assets are actually needed.

## Data Mapping Notes

The EPNM-style inventory uses these useful fields:

- `id`
- `name`
- `description`
- `type`
- `typeId`
- `physicalIndex`
- `containedPhysicalIndex`
- `operStatus`
- `serviceState`
- `serialNumber`
- `hardwareVersion`
- `manufacturer`
- `isFRUable`
- `slots.entry`
- `containingList`

Tree construction should use `containingList` recursively. Empty bays should still appear when present in chassis data, but visually distinguished from discovered modules.

Port mapping appears under `slots.entry` as interface names and port IDs. This should drive port-level details later.

## First Implementation Milestones

1. Asset audit script
   - Read `figures.tar.gz`.
   - Build a manifest of supported profiles, image paths, JSON paths, and pluggables.
   - Output a small report for the profiles we care about first.

2. Normalize ASR 903 sample
   - Convert `ASR-903_inventory.json` and `ASR-903_chassisdata.json` into our normalized schema.
   - Preserve parent/child hierarchy and physical index mapping.
   - Status: done for the first ASR 903 sample. The current normalizer uses `ASR-903_inventory.json`, `Cisco_ASR_903.json`, and `Cisco_ASR_903_Router.json` because slot geometry lives in the profile file, not the inventory sample.
   - Follow-up fix: slot coordinates are now normalized from the profile coordinate space into the actual chassis SVG `viewBox`, and slot assets prefer installed inventory `typeId` values over stale/default model entries.

3. Frontend component split
   - Move current Chassis View out of `InventoryPage.tsx`.
   - Remove fake actions.
   - Keep only real read-only controls.

4. Tree selection flow
   - Render inventory tree from normalized data.
   - Selecting tree node updates selected component state.
   - Details panel reads from selected component.
   - Status: done for component selection and aggregated descendant port counts.

5. Figure highlight flow
   - Render base equipment SVG/image.
   - Render hotspot overlay.
   - Selecting hotspot updates tree/details.
   - Selecting tree highlights hotspot.
   - Status: done for slot/module highlighting, including descendant selections such as transceivers/ports.

6. Port management surface
   - Aggregate direct and child-module ports for the selected component.
   - Show selectable port rows with port ID, parent module, and physical index.
   - Bind selected port by name/alias/ifIndex to persisted `/devices/{id}/managed-interfaces` when `deviceId` is available.
   - Show interface admin/oper state, speed, MAC, and role when the backend has a matching interface record.
   - Enable management entrypoints only when a live managed interface is bound:
     - run `show interface`
     - open monitoring policy workflow
     - open related alarms workflow
   - Status: workflow handoff done. Demo/example mode remains explicitly unbound and read-only. Live Chassis View passes device/interface context into Commands, Monitoring Policies, and Alarms; those destination pages now hydrate their forms/filters from the query params.

7. Add second profile
   - Add ASR 9906 or ASR 9006 to prove the model is not hardcoded to ASR 903.
   - Status: done for ASR 9006. The normalizer now supports `--profile asr9006`, emits `frontend/public/chassis-assets/asr9006/normalized.json`, extracts the ASR 9006 front SVG and pluggables, and registers the backend static profile at `backend/app/data/chassis/asr9006/normalized.json`.
   - Device detection now supports ASR 903 and ASR 9006 through `GET /api/devices/{device_id}/chassis`.

8. Connect to live inventory
   - Map collected backend inventory into the normalized chassis schema.
   - Use sample profile only as fallback/demo data.
   - Status: partial backend/frontend integration done. `DeviceDetailPage` mounts `ChassisView` in the Inventory tab for Cisco ASR 903 devices and passes the live `deviceId`.
   - `GET /api/devices/{device_id}/chassis` now returns the normalized chassis contract for supported ASR 903 devices, with live device identity over the static ASR 903 profile.
   - ENTITY-MIB collection path added: `POST /api/devices/{device_id}/chassis/collect` walks `entPhysicalTable`, persists normalized rows in `inventory.additional_info.physical_inventory`, and `GET /api/devices/{device_id}/chassis` overlays matching components by `physicalIndex`.
   - The UI now shows whether the loaded model is still static-profile based or enriched from Entity-MIB.
   - Physical inventory now has first-class storage in `physical_inventory_components` via Alembic revision `0014_physical_inventory_components`.
   - `chassis/collect` upserts ENTITY-MIB rows into the table, while still writing legacy `inventory.additional_info.physical_inventory` for compatibility.
   - `GET /api/devices/{device_id}/chassis` reads table rows first and falls back to legacy JSON only when the table has no collected components.

## Acceptance Criteria

- No visual-only fake actions in the main Chassis View.
- Discovered Elements is a real inventory tree.
- Clicking an inventory tree item highlights the matching chassis area.
- Clicking a chassis area selects the matching inventory tree item.
- Empty slots/bays are visible and clearly different from populated elements.
- Component detail panel reflects selected inventory data.
- The implementation supports at least two equipment profiles without hardcoded component layouts.
- Build, typecheck, and lint pass.
