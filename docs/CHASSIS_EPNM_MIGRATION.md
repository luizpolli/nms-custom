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
| asr920 | Generated simple | ⚠️ Needs EPNM SVG |
| ncs55a1 | Generated simple (13KB vs 930KB real) | ⚠️ Needs EPNM SVG |
| ncs560 | Generated simple | ⚠️ Needs EPNM SVG |
| ncs540 | Generated simple | ⚠️ Needs EPNM SVG |

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
1. NCS55A1 (equipo principal del usuario)
2. NCS560
3. NCS540
4. ASR920
