# EPNM Chassis View — Complete Device Model Catalog

All device models available in `docs/chassisview_figures/` with their SVGs, JSON configs, and views (front/rear).

Source: Cisco EPNM / Prime Infrastructure chassis view assets.

> **Total unique models (deduped): 95**
> **Total SVG files (chassis only, excl. pluggables): 347**

---

## ASR 1000 Family
| Model | Profile ID | SVGs | Views |
|-------|-----------|------|-------|
| ASR 1013 | `ASR1000/Cisco_ASR_1013_Router` | `ASR-1013-Front_Core.svg`, `ASR-1013-Rear-Core.svg` | Front + Rear |

## ASR 9000 Family (IOS XR / 64-bit)
Both `ASR9K-IOSXR` and `ASR9K-64CE` families share the same SVGs. Use `ASR9K-64CE` as canonical.

| Model | Profile ID | SVGs | Views |
|-------|-----------|------|-------|
| ASR 9000v (Virtual) | `Cisco_ASR_9000_V_Router` | `ASR-9000v.svg` | Front |
| ASR 9001 | `Cisco_ASR_9001_Router` | `ASR9001-Front.svg` | Front |
| ASR 9006 | `Cisco_ASR_9006_Router` | `ASR-9006-AC-Front.svg`, `ASR-9006-AC-V2-Front.svg` | Front (2 variants) |
| ASR 9010 | `Cisco_ASR_9010_Router` | `ASR-9010-AC-Front.svg`, `ASR-9010-AC-Front-V2.svg` | Front (2 variants) |
| ASR 9901 | `Cisco_ASR_9901_Router` | `asr9901-front_core.svg`, `asr9901-rear_core.svg` | Front + Rear |
| ASR 9902 | `Cisco_ASR_9902_Router` | `ASR-9902_front_core.svg`, `ASR-9902_rear_core.svg` | Front + Rear |
| ASR 9903 | `Cisco_ASR_9903_Router` | `ASR-9903_front_core.svg`, `ASR-9903_rear_core.svg` | Front + Rear |
| ASR 9904 | `Cisco_ASR_9904_Router` | `ASR-9904-Front.svg` | Front |
| ASR 9906 | `Cisco_ASR_9906_Router` | `ASR-9906-Front_core.svg`, `ASR-9906-Rear.svg` | Front + Rear |
| ASR 9910 | `Cisco_ASR_9910_Router` | `ASR-9910-Front.svg`, `ASR-9910-Rear.svg` | Front + Rear |
| ASR 9912 | `Cisco_ASR_9912_Router` | `ASR-9912-AC-Front.svg`, `ASR-9912-Rear.svg` | Front + Rear |
| ASR 9922 | `Cisco_ASR_9922_Router` | `ASR-9922-Front.svg` | Front |

**Pluggables:** `ASR9K-64CE/pluggables/` — line cards, RSPs, fan trays, power supplies

## ASR 900 / ASR 920 / NCS 42xx Family
Duplicated across `asr901Family`, `asr901sFamily`, `asr90xFamily`, `NCS42XXFamily` (same SVGs). Use `NCS42XXFamily` as canonical.

### ASR 901S Series (Small Cell)
| Model | SVGs | Views |
|-------|------|-------|
| ASR 901S-2SG-F-AH | `A901S-2SG-F-AH-Front.svg`, `A901S-2SG-F-AH-Rear.svg` | Front + Rear |
| ASR 901S-2SG-F-D | `A901S-2SG-F-D-Front.svg`, `A901S-2SG-F-D-Rear.svg` | Front + Rear |
| ASR 901S-3SG-F-AH | `A901S-3SG-F-AH_Front.svg`, `A901S-3SG-F-AH-Rear.svg` | Front + Rear |
| ASR 901S-3SG-F-D | `A901S-3SG-F-D-Front.svg`, `A901S-3SG-F-D-Rear.svg` | Front + Rear |
| ASR 901S-4SG-F-D | `A901S-4SG-F-D-Front.svg`, `A901S-4SG-F-D-Rear.svg` | Front + Rear |

### ASR 902 / 903 / 907
| Model | SVGs | Views |
|-------|------|-------|
| ASR 902 | `ASR-902-Front.svg`, `ASR-902-Rear.svg` | Front + Rear |
| ASR 902U | `ASR-902U-Front.svg`, `ASR-902U-Rear.svg` | Front + Rear |
| ASR 903 | `ASR-903-Front.svg` | Front |
| ASR 903U | `ASR-903U-Front.svg` | Front |
| ASR 907 | `ASR-907-Front.svg` | Front |

### ASR 920 Series
| Model | SVGs | Views |
|-------|------|-------|
| ASR-920-20SZ-M | `ASR-920-20SZ-M-Front-Core.svg` | Front |
| ASR-920-12SZ-A | `ASR-920-12SZ-A_front_core.svg` | Front |
| ASR-920-12SZ-D | `ASR-920-12SZ-D_front_core.svg` | Front |
| ASR-920-12SZ-IM | `ASR-920-12SZ-IM-Front.svg` | Front |
| ASR-920U-12SZ-IM | `ASR-920U-12SZ-IM-Front.svg` | Front |
| ASR-920-10SZ-PD | `ASR-920-10SZ-PD-Front.svg` | Front |
| ASR-920-8S4Z-PD | `ASR-920-8S4Z-PD_core.svg` | Front |
| ASR-920-4SZ-A | `ASR-920-4SZ-A-Front.svg` | Front |
| ASR-920-4SZ-D | `ASR-920-4SZ-D-Front.svg` | Front |
| ASR-920-12CZ-A | `ASR-920-12CZ-A-Front.svg` | Front |
| ASR-920-12CZ-D | `ASR-920-12CZ-D-Front.svg` | Front |
| ASR-920-24SZ-IM | `ASR-920-24SZ-IM-Front.svg` | Front |
| ASR-920-24SZ-M | `ASR-920-24SZ-M-Front.svg` | Front |
| ASR-920-24TZ-M | `ASR-920-24TZ-M-Front.svg` | Front |

### NCS 42xx
| Model | SVGs | Views |
|-------|------|-------|
| NCS 4201 | `NCS-4201-Front.svg` | Front |
| NCS 4202 | `NCS-4202-Front.svg` | Front |
| NCS 4206 | `NCS-4206-Front.svg` | Front |
| NCS 4216 | `NCS-4216-Front.svg`, `NCS4216-Rear.svg` | Front + Rear |
| NCS 4216 F2B | `NCS4216-F2B-SA-Front.svg` | Front |

## NCS 5500 / NCS 55xx Family (`NCS55XX_CE`)

### NCS 55A1 Series
| Model | SVGs | Views |
|-------|------|-------|
| NCS 55A1-24H | `NCS-55A1-24H_Front.svg`, `NCS-55A1-24H_Rear_core.svg` | Front + Rear |
| NCS 55A1-24Q6H-S | `NCS-55A1-24Q6H-S-Front_core.svg`, `NCS-55A1-24Q6H-S-Rear_core.svg` | Front + Rear |
| NCS 55A1-24Q6H-SS | `NCS-55A1-24Q6H-SS-Front_core.svg`, `NCS-55A1-24Q6H-S-Rear_core.svg` | Front + Rear |
| **NCS 55A1-36H-S** | `NCS-55A1-36H-S_Front.svg`, `NCS-55A1-36H-S_Rear_core.svg` | Front + Rear |
| **NCS 55A1-36H-SE-S** ⭐ | `NCS-55A1-36H-SE_Front.svg`, `NCS-55A1-36H-S_Rear_core.svg` | Front + Rear |
| NCS 55A1-48Q6H | `NCS-55A1-48Q6H-Front_core.svg`, `NCS-55A1-48Q6H-Rear_core.svg` | Front + Rear |

### NCS 55A2 Series (Modular)
| Model | SVGs | Views |
|-------|------|-------|
| NCS 55A2-MOD-S | `NCS-55A2-MOD-SE-S_Front_core.svg`, `NCS-55A2-MOD-S_Rear_core.svg` | Front + Rear |
| NCS 55A2-MOD-SE-S | `NCS-55A2-MOD-SE-S_Front_core.svg`, `NCS-55A2-MOD-SE-S_Rear_core.svg` | Front + Rear |
| NCS 55A2-MOD-SE-H-S | `NCS-55A2-MOD-SE-S_Front_core.svg`, `NCS-55A2-MOD-SE-S_Rear_core.svg` | Front + Rear |
| NCS 55A2-MOD-HD-S | `NCS-55A2-MOD-HD-S_Front_core.svg`, `NCS-55A2-MOD-HD-S_Rear_core.svg` | Front + Rear |
| NCS 55A2-MOD-HX-S | `NCS-55A2-MOD-HD-S_Front_core.svg`, `NCS-55A2-MOD-HD-S_Rear_core.svg` | Front + Rear |

### NCS 5500 Modular Chassis
| Model | SVGs | Views |
|-------|------|-------|
| NCS 5501 | `NCS-5501-Front-core.svg`, `NCS-5501_Rear_core.svg` | Front + Rear |
| NCS 5501-SE | `NCS-5501-SE-Front-core.svg`, `NCS-5501-SE-Rear.svg` | Front + Rear |
| NCS 5502 | `NCS-5502_Front_core.svg`, `NCS-5502-Rear-core.svg` | Front + Rear |
| NCS 5502-SE | `NCS-5502-SE_Front_core.svg`, `NCS-5502-SE-Rear-core.svg` | Front + Rear |
| NCS 5504 | `NCS-5504-FRONT_CORE.svg`, `NCS-5504-REAR_CORE.svg` | Front + Rear |
| NCS 5508 | `NCS-5508-Front_b.svg`, `NCS-5508-Rear_b.svg` | Front + Rear |
| NCS 5516 | `NCS-5516-Front-Core.svg`, `ncs-5516-rear_core.svg` | Front + Rear |

### NCS 560 Series ⭐
| Model | SVGs | Views |
|-------|------|-------|
| **NCS 560** ⭐ | `N560-Front.svg` | Front |
| NCS 560 Enhanced | `N560-Front.svg` | Front |
| NCS 560-4 | `NCS560-4-front_core.svg` | Front |
| NCS 560-4 RSP4 | `N560-Front.svg`, `NCS560-4-front_core.svg` | Front (2 variants) |
| NCS 560-4 RSP4E CC | `NCS560-4-front_core.svg` | Front |
| NCS 560-4 RSP4 CC | `NCS560-4-front_core.svg` | Front |

### NCS 540 in NCS55XX_CE
| Model | SVGs | Views |
|-------|------|-------|
| NCS 540-24Z8Q2C-M | `N540-24Z8Q2C-M_Front.svg`, `N540-24Z8Q2C-M_Rear.svg` | Front + Rear |
| NCS 540-ACC-SYS | `N540-ACC-SYS_Front.svg`, `N540-ACC-SYS_Rear.svg` | Front + Rear |
| NCS 540X-ACC-SYS | `N540X-ACC-SYS_Front.svg`, `N540X-ACC-SYS_Rear.svg` | Front + Rear |

### NCS 57xx Series
| Model | SVGs | Views |
|-------|------|-------|
| NCS-57C3-MOD-SYS | `NCS-57C3-MOD-S_Front_Core.svg`, `NC57-C3-FAN2-FW_Rear_Core.svg` | Front + Rear |
| NCS-57C3-MODS-SYS | `NCS-57C3-MOD-S_Front_Core.svg`, `NC57-C3-FAN2-FW_Rear_Core.svg` | Front + Rear |

## NCS 540L / Cisco 8000 Series (`NCS540L_CE`)

### NCS 540 (Large variants)
| Model | SVGs | Views |
|-------|------|-------|
| N540-24Q2C2DD-SYS | `N540-24Q2C2DD-SYS_front_core.svg`, `N540-24Q2C2DD-SYS_rear_core.svg` | Front + Rear |
| NCS 540-12Z20G-SYS-A | `N540-12Z20G-SYS-A_Front_core.svg`, `N540-12Z20G-SYS-A_rear_core.svg` | Front + Rear |
| NCS 540-12Z20G-SYS-D | `N540-12Z20G-SYS-D_front_core.svg`, `N540-12Z20G-SYS-D_rear_core.svg` | Front + Rear |
| NCS 540-24Q8L2DD-SYS-A | `N540-24Q8L2DD-SYS_front_core.svg`, `N540-24Q8L2DD-SYS_rear_core.svg` | Front + Rear |
| NCS 540-28Z4C-SYS-A | `N540-28Z4C-SYS-A_front_core.svg` | Front |
| NCS 540-28Z4C-SYS-D | `N540-28Z4C-SYS-D_front_core.svg` | Front |
| NCS 540-6Z18G-SYS-A | `N540-6Z18G-SYS-A_Core.svg` | Front |
| NCS 540-6Z18G-SYS-D | `N540-6Z18G-SYS-D_Core.svg` | Front |
| NCS 540-FH-AGG-SYS | `N540-FH-AGG-SYS_Front_Core.svg`, `N540-FH-AGG-SYS_Rear_Core.svg` | Front + Rear |
| NCS 540-FH-CSR-SYS | `N540-FH-CSR-SYS_Front_Core.svg`, `N540-FH-CSR-SYS_Rear_Core.svg` | Front + Rear |
| NCS 540X-12Z16G-SYS-A | `N540X-12Z16G-SYS-A_Front_core.svg` | Front |
| NCS 540X-12Z16G-SYS-D | `N540X-12Z16G-SYS-D_Front_core.svg` | Front |
| NCS 540X-16Z4G8Q2C-A | `N540X-16Z4G8Q2C-A_Front_core.svg` | Front |
| NCS 540X-16Z4G8Q2C-D | `N540X-16Z4G8Q2C-D_Front_core.svg` | Front |
| NCS 540X-16Z8Q2C-D | `N540X-16Z8Q2C-D_front_core.svg` | Front |
| NCS 540X-4Z14G2Q-A | `N540X-4Z14G2Q-A_front_core.svg` | Front |
| NCS 540X-4Z14G2Q-D | `N540X-4Z14G2Q-D_font_core.svg` | Front |
| NCS 540X-6Z14S-SYS-D | `N540-6Z14S-SYS-D_core.svg` | Front |
| NCS 540X-6Z18G-SYS-A | `N540-6Z18G-SYS-A_front_core.svg` | Front |
| NCS 540X-6Z18G-SYS-D | `N540-6Z18G-SYS-D_front_core.svg` | Front |
| NCS 540X-8Z16G-SYS-A | `N540-8Z16G-SYS-A_front_core.svg` | Front |
| NCS 540X-8Z16G-SYS-D | `N540-8Z16G-SYS-D_front_core.svg` | Front |

### NCS 57xx (in NCS540L_CE)
| Model | SVGs | Views |
|-------|------|-------|
| NCS-57B1-5DSE-SYS | `NCS-57B1-5DSE-SYS_Front_core.svg`, `NCS-57B1-5DSE-SYS_Rear_core.svg` | Front + Rear |
| NCS-57B1-6D24-SYS | `NCS-57B1-6D24-SYS_Front_core.svg`, `NCS-57B1-6D24-SYS_Rear_core.svg` | Front + Rear |
| NCS-57C1-48Q6-SYS | `NCS-57C1-48Q6-SYS_front_core.svg`, `NCS-57C1-48Q6-SYS_rear_core.svg` | Front + Rear |
| NCS-57D2-18DD-SYS | `NCS-57D2-18DD-SYS_front_core.svg`, `NCS-57D2-18DD-SYS_rear_core.svg` | Front + Rear |

### Cisco 8000 Series (Silicon One)
| Model | SVGs | Views |
|-------|------|-------|
| 8011-2X2XP4L (PLE NID) | `8011-2X2XP4L_front_core.svg`, `8011-2X2XP4L_rear_core.svg` | Front + Rear |
| 8011-4G24Y4H-I | `8011-4G24Y4H-I_front_core.svg`, `8011-4G24Y4H-I_rear_core.svg` | Front + Rear |
| 8101-32FH | `8101-32FH-front_core.svg`, `8101-32FH-rear_core.svg` | Front + Rear |
| 8111-32EH | `8111-32EH-front_core.svg`, `8111-32EH-rear_core.svg` | Front + Rear |
| 8201 | `Cisco-8201-SYS-front_core.svg`, `Cisco-8201-SYS-rear_core.svg` | Front + Rear |
| 8201-24H8FH | `8201-24H8FH-front_core.svg`, `8201-24H8FH-rear_core.svg` | Front + Rear |
| 8201-32FH | `8201-32FH-front_core.svg`, `8201-32FH-rear_core.svg` | Front + Rear |
| 8202 | `8202-SYS_front_core.svg`, `8202-SYS_rear_core.svg` | Front + Rear |
| 8202-32FH-M | `8202-32FH-M_front_core.svg`, `8202-32FH-M_rear_core.svg` | Front + Rear |
| 8212-48FH-M | `8212-48FH-M_front_core.svg`, `8212-48FH-M_rear_core.svg` | Front + Rear |
| 8608 | `8608-SYS_Front_Core.svg`, `8608-SYS_Rear_Core.svg` | Front + Rear |
| 8711-32FH-M | `8711-32FH-M-front_core.svg`, `8711-32FH-M-rear_core.svg` | Front + Rear |
| 8712-MOD-M | `8712-MOD-M_front_core.svg`, `8712-MOD-M_rear_core.svg` | Front + Rear |
| 8804 | `8804-SYS_front_core.svg`, `8804-SYS_rear_core.svg` | Front + Rear |
| 8808 | `8808-SYS_front_core.svg`, `8808-SYS_rear_core.svg` | Front + Rear |
| 8812 | `8812-SYS_front_core.svg`, `8812-SYS_rear_core.svg` | Front + Rear |
| 8818 | `8818-SYS_front_core.svg`, `8818-SYS_rear_core.svg` | Front + Rear |

## NCS 5000 Family (`NCS5K`)
| Model | SVGs | Views |
|-------|------|-------|
| NCS 5001 | `NCS5001-Front.svg`, `NCS5001-Rear.svg` | Front + Rear |
| NCS 5002 | `NCS5002-Front.svg`, `NCS5002-Rear.svg` | Front + Rear |
| NCS 5011 | `NCS5011-Front-Core.svg`, `NCS-5011_Rear.svg` | Front + Rear |

## NCS 520 (`NCS520CE`)
| Model | SVGs | Views |
|-------|------|-------|
| NCS 520-4G4Z-A | `N520-X-4G4Z-A.svg` | Front |
| NCS 520-X-4G4Z-A | `N520-X-4G4Z-A.svg` | Front |
| NCS 520-X-4G4Z-D | `N520-X-4G4Z-D_core.svg` | Front |

## NCS 6000 (`ncs6008`)
| Model | SVGs | Views |
|-------|------|-------|
| NCS 6008 | `NCS-6008-Front.svg`, `NCS-6008-Rear.svg` | Front + Rear |

## CBR-8 (`CBR8`)
| Model | SVGs | Views |
|-------|------|-------|
| cBR-8 CCAP | `CBR-8-CCAP-CHASS-Front.svg`, `CBR-8-CCAP-CHASS-Rear.svg` | Front + Rear |

## CRS-1 (`CRS16SB`)
| Model | SVGs | Views |
|-------|------|-------|
| CRS-1 16-Slot | `CRS-16-Front_core.svg`, `CRS-16-Rear_core.svg` | Front + Rear |
| CRS-1 8-Slot | `CRS-1_8-core.svg`, `CRS-1_8-rear_core.svg` | Front + Rear |

## ME 1200 (`ME1200CE`)
| Model | SVGs | Views |
|-------|------|-------|
| ME 1200-4S-A | `ME1200-4S-A.svg`, `ME1200-4S-D.svg` | Front (2 variants) |

## Catalyst 6500 (`cat6500`)
| Model | SVGs | Views |
|-------|------|-------|
| Catalyst 6504-E | `WS-C6504-E_Front.svg`, `C6504-E_Rear_core.svg` | Front + Rear |
| Catalyst 6509 | `WS-C6509-E-core.svg` | Front |
| Catalyst 6500 VSS | `WS-C6504-E_Front.svg`, `C6504-E_Rear_core.svg` | Front + Rear |

## Rack (`com.cisco.nms.chassis.nms-chassis-resource-rack`)
| Model | Notes |
|-------|-------|
| Cisco R42610 | Generic rack chassis container |
| RACK | Generic rack container |

---

## Pluggable Libraries (shared line cards, fans, PSUs)

Each device family has a `pluggables/` directory with shared component SVGs:

| Family | Pluggable Dir | Notable Components |
|--------|--------------|-------------------|
| `ASR1000` | `pluggables/images/` | ASR1000 ESPs, SIPs, RPs |
| `ASR9K-64CE` | `pluggables/images/` | A9K line cards, RSPs, fans, PSUs |
| `NCS42XXFamily` | `pluggables/images/` | A900 IMAs, RSPs, fans, PSUs |
| `NCS55XX_CE` | `pluggables/images/horizontal/` | N560 line cards/fans/PSUs, N540 RPs |
| `NCS540L_CE` | `pluggables/images/` | 8000-series line cards, fans |
| `NCS5K` | `pluggables/images/` | NCS 5K line cards |
| `CBR8` | `pluggables/images/` | CBR-8 cards |
| `CRS16SB` | `pluggables/images/` | CRS line cards |
| `cat6500` | `pluggables/images/` | Sup engines, line cards |
| `ncs6008` | `pluggables/images/` | NCS 6K line cards |

## Shared UI Assets (`chassis/svg/images/`)

Status/overlay icons for chassis view rendering:
- `fi-normal.svg`, `fi-warning.svg`, `fi-info.svg` — Status indicators
- `fi-record-critical.svg`, `fi-record-major.svg`, `fi-record-minor.svg`, `fi-record-warning.svg`, `fi-record-information.svg` — Alarm severity markers
- `alertCritical.svg`, `alertMajor.svg`, `alertMinor.svg` — Alert badges
- `up.svg`, `down.svg`, `unknown.svg` — Port status
- `fi-admindown.svg`, `auto-up.svg` — Interface admin states
- `hightlightPort.svg`, `highlightPort_static.svg` — Port selection highlights
- `fiext_port_critical.svg`, `fiext_port_major.svg`, `fiext_port_minor.svg`, `fiext_port_warning.svg`, `fiext_port_information.svg` — Port-level severity
- `icon_chassis_view_front.svg`, `icon_chassis_view_rear.svg` — View toggle icons

---

⭐ = Models currently in use in nms-custom
