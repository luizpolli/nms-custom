# Chassis View: Migración a Assets Reales de EPNM

## Problema
Los SVGs para NCS55A1, NCS560, NCS540 y ASR920 fueron generados desde cero (simplificados, ~13KB) en vez de usar los assets reales de Cisco EPNM/Prime que ya existen en el repo.

## Ubicación de assets reales
```
docs/chassisview_figures/
├── chassis/           # Legacy format (asr900, asr9k families)
│   ├── data/          # JSON con slot definitions + linecards
│   └── svg/           # SVGs compartidos + images (status icons, etc.)
├── chassisview/       # EPNM format (com.cisco.prime.deviceprofile)
│   └── com.cisco.prime.deviceprofile/
│       ├── NCS55XX_CE/          # NCS55A1, NCS560, NCS5501, NCS5502, etc.
│       │   ├── Cisco_NCS_55A1-36H-SE-S/  # Our model
│       │   │   ├── data/Cisco_NCS_55A1-36H-SE-S.json  # Slot definitions
│       │   │   └── images/NCS-55A1-36H-SE_Front.svg    # 930KB real SVG!
│       │   ├── Cisco_NCS_560_Router/
│       │   │   ├── data/Cisco_NCS_560_Router.json
│       │   │   └── images/N560-Front.svg
│       │   └── pluggables/
│       │       ├── data/pluggables.json
│       │       └── images/horizontal/   # Line card, fan, PSU SVGs
│       ├── ASR9K-64CE/          # ASR9K family (already used for ASR9010)
│       ├── NCS42XXFamily/       # ASR903, ASR907, ASR920 variants, NCS42xx
│       ├── NCS540L_CE/          # NCS540 variants (LOTS of sub-models)
│       └── asr901Family/       # ASR901/902/903/907/920 variants
└── ...
```

## Estado actual
| Profile | SVG Source | Status |
|---------|-----------|--------|
| asr903 | EPNM real | ✅ OK |
| asr9006 | EPNM real | ✅ OK |
| asr9010 | EPNM real (78KB match) | ✅ OK |
| asr920 | EPNM real | ✅ OK |
| ncs55a1 | EPNM real | ✅ OK |
| ncs560 | EPNM real | ✅ OK |
| ncs540 | EPNM real | ✅ OK |
| ncs540-16z4 (N540X-16Z4G8Q2C-D, -A) | EPNM real — 4 hotspots (fan, RP, PM0, PM1) | ✅ Done |
| ncs540-12z16g (N540X-12Z16G-SYS-D, -A) | EPNM real — 3 hotspots (RP, PM0, PM1) | ✅ Done |
| ncs540-28z4c (N540-28Z4C-SYS-D, -A) | EPNM real — 3 hotspots (RP, PM0, PM1) | ✅ Done |
| ncs540-12z20g (N540-12Z20G-SYS-D, -A) | EPNM real — 4 hotspots (fan, RP, PM0, PM1) | ✅ Done |
| ncs540-fh-agg (N540-FH-AGG-SYS) | EPNM real — 4 hotspots (PSU0, PSU1, RP, fan) | ✅ Done |
| ncs540-fh-csr (N540-FH-CSR-SYS) | EPNM real — 4 hotspots (PSU0, PSU1, fan, RP) | ✅ Done |
| ncs540x-4z14g2q (N540X-4Z14G2Q-D, -A) | EPNM real — 3 hotspots (PM0, PM1, RP) | ✅ Done |

### NCS540L_CE family — completed sub-models

| Profile key | Model(s) | Build script | Hotspots | Notes |
|---|---|---|---|---|
| `ncs540-16z4` | N540X-16Z4G8Q2C-D, **-A** alias | `scripts/build_ncs540_16z4_chassis_profile.py` | 4 (fan, RP, PM0, PM1) | SNMP walk: `ncs540-16z4-entity-mib.json` |
| `ncs540-12z16g` | N540X-12Z16G-SYS-D, **-A** alias | `scripts/build_ncs540_12z16g_chassis_profile.py` | 3 (RP, PM0, PM1) | Component data reused from `ncs540`; fan slot not in EPNM front view |
| `ncs540-28z4c` | N540-28Z4C-SYS-D, **-A** alias | `scripts/build_ncs540_remaining_variants.py` | 3 (RP, PM0, PM1) | Component data reused from `ncs540` |
| `ncs540-12z20g` | N540-12Z20G-SYS-D, **-A** alias | `scripts/build_ncs540_remaining_variants.py` | 4 (fan, RP, PM0, PM1) | Component data reused from `ncs540` |
| `ncs540-fh-agg` | N540-FH-AGG-SYS | `scripts/build_ncs540_remaining_variants.py` | 4 (PSU0, PSU1, RP, fan) | Component data reused from `ncs540` |
| `ncs540-fh-csr` | N540-FH-CSR-SYS | `scripts/build_ncs540_remaining_variants.py` | 4 (PSU0, PSU1, fan, RP) | Component data reused from `ncs540` |
| `ncs540x-4z14g2q` | N540X-4Z14G2Q-D, **-A** alias | `scripts/build_ncs540_remaining_variants.py` | 3 (PM0, PM1, RP) | Component data reused from `ncs540` |

Detection rules in `backend/app/api/devices.py::_chassis_profile_for_device`:
- `"16z4" in compact_terms and "540x" in compact_terms` → `ncs540-16z4` (D + A variants)
- `"12z16g" in compact_terms and "540x" in compact_terms` → `ncs540-12z16g` (D + A variants)
- `"28z4c" in compact_terms and "n540" in compact_terms` → `ncs540-28z4c` (D + A variants)
- `"12z20g" in compact_terms and "n540" in compact_terms` → `ncs540-12z20g` (D + A variants)
- `"fhagg" in compact_terms and "n540" in compact_terms` → `ncs540-fh-agg`
- `"fhcsr" in compact_terms and "n540" in compact_terms` → `ncs540-fh-csr`
- `"4z14g2q" in compact_terms and "540x" in compact_terms` → `ncs540x-4z14g2q` (D + A variants)
- Generic `ncs540` fallback for all other N540/NCS540 strings.

### NCS540L_CE family — not migrated (no usable EPNM slot data)

| Model | Reason |
|---|---|
| N540-24Q2C2DD-SYS | EPNM JSON has no slot definitions; no SVG slot coordinates |
| N540-6Z18G-SYS-A/D | EPNM JSON has no `svgImageId` or slot defs (only SVG file present) |
| N540X-16Z8Q2C-D | EPNM JSON has no slot definitions |
| N540X-6Z14S-SYS-D | EPNM JSON has no slot definitions |
| N540-24Q8L2DD-SYS-A | EPNM slot data present but no matching pluggable SVGs; deferred |
| N540X-6Z18G-SYS-D/A, N540X-8Z16G-SYS-D/A | Same SVG layout as 4Z14G2Q; fall back to generic `ncs540` |
| NCS-57B1/57C1/57D2 (NCS57xx) | Different family — out of NCS540L_CE migration scope |
| Cisco 8000 series (17 models) | Different family — out of NCS540L_CE migration scope |

## Plan de migración

### Para cada perfil que necesita actualización:

1. **Copiar SVG real** de `docs/chassisview_figures/.../images/` → `frontend/public/chassis-assets/{profile}/`
2. **Parsear JSON de EPNM** — formato es JS object (no strict JSON), tiene:
   - `views[].containers` → slot definitions con `x, y, width, height` coordinates
   - `slots` → mapping de slot names a coordenadas para hotspot generation
   - `pluggables` reference → SVGs de line cards insertables
3. **Re-generar normalized.json** — mapear EPNM slot coordinates → nuestro formato de hotspots
4. **Copiar pluggable SVGs** relevantes → para asset overlay en ChassisView
5. **Verificar** hotspots clickeables en el browser

### JSON EPNM format (ejemplo NCS55A1):
```javascript
{
  id: "Cisco NCS 55A1-36H-SE-S",
  views: [{
    id: "front",
    containers: {
      "NCS-55A1-36H-SE-S": {
        svgImageId: "NCS-55A1-36H-SE_Front.svg",
        height: 125, width: 1120,
        slots: {
          "Rack_0-RouteProcessor_Slot_0": { x: 40, y: 5, alias: 0 },
          // ... more slots
        }
      }
    }
  }]
}
```

### Nuestro normalized.json format:
```json
{
  "views": [{
    "id": "front",
    "image": "NCS-55A1-36H-SE_Front.svg",
    "width": 1120, "height": 125,
    "hotspots": [
      { "id": "slot-rp0", "slotKey": "0/RP0", "label": "RP 0",
        "bounds": { "x": 3.57, "y": 4.0, "w": 10.0, "h": 92.0 },
        "inventoryId": "component-rp0", "physicalIndex": "1" }
    ]
  }]
}
```

### Script de conversión necesario:
`scripts/convert_epnm_chassis_profile.py` — que tome:
- Input: path al directorio EPNM del device profile
- Output: `normalized.json` con hotspots mapeados + SVGs copiados

## Bonus: Assets disponibles que no estamos usando
- **Rear views** — varios modelos tienen SVG trasero
- **Pluggable SVGs** — line cards individuales (A9K-MOD80, A903-RSP1A, N560-IMA2C, etc.)
- **Status overlay icons** — `fi-normal.svg`, `fi-warning.svg`, etc. en `chassis/svg/images/`
- **Muchos más modelos** — NCS5501, NCS5508, ASR9901/9902/9903, Cat6500, NCS1001, etc.

## Prioridad
1. NCS55A1 (equipo principal del usuario) — ✅ done
2. NCS560 — ✅ done
3. NCS540 — ✅ done
4. ASR920 — ✅ done
5. **NCS540L_CE family** — ✅ done (7 profiles: `ncs540-16z4`, `ncs540-12z16g`, `ncs540-28z4c`, `ncs540-12z20g`, `ncs540-fh-agg`, `ncs540-fh-csr`, `ncs540x-4z14g2q`; variants without EPNM slot data fall back to generic `ncs540`)
6. ASR9010 — ✅ done
7. NCS55A1 additional variants — ✅ done (see below)
8. NCS5500 fixed-port family — ✅ done (NCS-5501, NCS-5502, NCS-5508)

---

## NCS55A1 Additional Variants (added 2026-05-30)

Static visual profiles — front + rear views — for NCS55A1 sub-models without dedicated SNMP walk data. Slots shown are based on EPNM SVG assets and slot coordinates from `NCS55XX_CE/js/ChassisViewMetaDataV2.js`.

| Profile | Models | Front SVG | Rear SVG | Notes |
|---|---|---|---|---|
| `ncs55a1-24h` | NCS-55A1-24H | `NCS-55A1-24H_Front.svg` | `NCS-55A1-24H_Rear_core.svg` | 1RU, 2 PSU + 2 FT rear |
| `ncs55a1-24q6h` | NCS-55A1-24Q6H-S, NCS-55A1-24Q6H-SS | `NCS-55A1-24Q6H-S-Front_core.svg` | `NCS-55A1-24Q6H-S-Rear_core.svg` | 1RU, 2 PSU + 2 FT rear |
| `ncs55a1-48q6h` | NCS-55A1-48Q6H | `NCS-55A1-48Q6H-Front_core.svg` | `NCS-55A1-48Q6H-Rear_core.svg` | 1RU, 2 PSU + 2 FT rear |

Detection rules:
- `"48q6h" in compact_terms and "ncs55a1" in compact_terms` → `ncs55a1-48q6h`
- `"24q6h" in compact_terms and "ncs55a1" in compact_terms` → `ncs55a1-24q6h`
- `"24h" in compact_terms and "ncs55a1" in compact_terms` → `ncs55a1-24h`
- Generic `ncs55a1` fallback for 36H-S, 36H-SE-S and any other NCS-55A1 model.

---

## NCS5500 Fixed-Port Router Family (added 2026-05-30)

| Profile | Models | Front SVG | Rear SVG | Form Factor |
|---|---|---|---|---|
| `ncs5501` | NCS-5501, NCS-5501-SE | `NCS-5501-Front-core.svg` | `NCS-5501_Rear_core.svg` | 1RU |
| `ncs5502` | NCS-5502, NCS-5502-SE | `NCS-5502_Front_core.svg` | `NCS-5502-Rear-core.svg` | 2RU |
| `ncs5508` | NCS-5508 | `NCS-5508-Front_b.svg` | `NCS-5508-Rear_b.svg` | Modular (8-slot) |

Detection rules (all checked before `ncs55a1`):
- `"ncs5508" in compact_terms` → `ncs5508`
- `"ncs5516" in compact_terms` → `ncs5516` *(profile not yet created, returns None)*
- `"ncs5502" in compact_terms` → `ncs5502`
- `"ncs5501" in compact_terms` → `ncs5501`

---

## Front/Rear View Switcher (Frontend)

`ChassisView.tsx` was updated to support multi-view profiles. When `data.views.length > 1`, a **Front View / Rear View** toggle appears above the chassis diagram. Both the header display and the `ChassisCanvas` component respect the selected view id.

All existing single-view profiles (`asr9006`, `asr9010`, etc.) are unaffected — the toggle only appears when there are multiple views.
