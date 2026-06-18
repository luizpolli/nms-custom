import { DEV, CRED } from './devices';

const OLDER = (d: number) => new Date(Date.now() - d * 86400000).toISOString();

// ─── Credentials ─────────────────────────────────────────────────────────────

export const DEMO_CREDENTIALS = [
  {
    id: CRED.SNMPv3,
    name: 'SNMPv3-NCS-Core',
    hostname: '',
    username: 'nms_snmpv3',
    protocol: 'snmpv3',
    snmp_version: 3,
    port: 161,
    has_secret: true,
    created_at: OLDER(30),
    updated_at: OLDER(5),
  },
  {
    id: CRED.SNMPv2c,
    name: 'SNMPv2c-Legacy',
    hostname: '',
    username: '',
    protocol: 'snmpv2c',
    snmp_version: 2,
    port: 161,
    has_secret: true,
    created_at: OLDER(60),
    updated_at: OLDER(10),
  },
  {
    id: CRED.SSH_CLI,
    name: 'SSH-CLI-IOS',
    hostname: '',
    username: 'cisco_nms',
    protocol: 'ssh',
    snmp_version: null,
    port: 22,
    has_secret: true,
    created_at: OLDER(45),
    updated_at: OLDER(7),
  },
  {
    id: CRED.TACACS,
    name: 'TACACS-BCS',
    hostname: 'tacacs.bcs.cisco.com',
    username: '',
    protocol: 'tacacs',
    snmp_version: null,
    port: 49,
    has_secret: true,
    created_at: OLDER(90),
    updated_at: OLDER(15),
  },
];

// ─── Services ────────────────────────────────────────────────────────────────

export const DEMO_SERVICES = [
  {
    id: 'svc-0001',
    name: 'VPLS-ATT-CDMX-Ring',
    description: 'AT&T VPLS ring service — CDMX metro area',
    service_type: 'vpls',
    status: 'active',
    created_at: OLDER(120),
    updated_at: OLDER(2),
    members: [
      { id: 'sm-001', device_id: DEV.NCS55_CDMX, role: 'pe', weight: 1 },
      { id: 'sm-002', device_id: DEV.NCS560_CDMX, role: 'p', weight: 1 },
    ],
    dependencies: [],
  },
  {
    id: 'svc-0002',
    name: 'L3VPN-CORP-BACKBONE',
    description: 'Corporate backbone L3VPN — CDMX/GDL/MTY',
    service_type: 'l3vpn',
    status: 'active',
    created_at: OLDER(180),
    updated_at: OLDER(3),
    members: [
      { id: 'sm-003', device_id: DEV.ASR9010_1, role: 'pe', weight: 1 },
      { id: 'sm-004', device_id: DEV.ASR9010_2, role: 'pe', weight: 1 },
      { id: 'sm-005', device_id: DEV.ASR9010_3, role: 'pe', weight: 1 },
    ],
    dependencies: ['svc-0003'],
  },
  {
    id: 'svc-0003',
    name: 'MPLS-CORE-TRANSPORT',
    description: 'MPLS TE core transport — all regions',
    service_type: 'mpls-te',
    status: 'degraded',
    created_at: OLDER(200),
    updated_at: OLDER(0),
    members: [
      { id: 'sm-006', device_id: DEV.NCS55_CDMX, role: 'core', weight: 2 },
      { id: 'sm-007', device_id: DEV.NCS55_GDL,  role: 'core', weight: 2 },
      { id: 'sm-008', device_id: DEV.NCS55_MTY,  role: 'core', weight: 2 },
    ],
    dependencies: [],
  },
  {
    id: 'svc-0004',
    name: 'METRO-E-CDMX-NORTH',
    description: 'Metro Ethernet service — CDMX North cluster',
    service_type: 'metro-e',
    status: 'active',
    created_at: OLDER(90),
    updated_at: OLDER(4),
    members: [
      { id: 'sm-009', device_id: DEV.ASR920_1, role: 'access', weight: 1 },
      { id: 'sm-010', device_id: DEV.ASR920_2, role: 'access', weight: 1 },
    ],
    dependencies: ['svc-0001'],
  },
  {
    id: 'svc-0005',
    name: '4G-PGW-CDMX',
    description: 'Mobile 4G PGW service — CDMX cluster',
    service_type: 'mobile-gw',
    status: 'active',
    created_at: OLDER(300),
    updated_at: OLDER(5),
    members: [
      { id: 'sm-011', device_id: DEV.ASR5K_1, role: 'pgw', weight: 2 },
    ],
    dependencies: ['svc-0003'],
  },
  {
    id: 'svc-0006',
    name: '4G-PGW-GDL',
    description: 'Mobile 4G PGW service — GDL cluster',
    service_type: 'mobile-gw',
    status: 'active',
    created_at: OLDER(295),
    updated_at: OLDER(6),
    members: [
      { id: 'sm-012', device_id: DEV.ASR5K_2, role: 'pgw', weight: 2 },
    ],
    dependencies: ['svc-0003'],
  },
  {
    id: 'svc-0007',
    name: 'VPLS-ATT-GDL-Ring',
    description: 'AT&T VPLS ring service — GDL metro area',
    service_type: 'vpls',
    status: 'active',
    created_at: OLDER(110),
    updated_at: OLDER(7),
    members: [
      { id: 'sm-013', device_id: DEV.NCS55_GDL,  role: 'pe', weight: 1 },
      { id: 'sm-014', device_id: DEV.NCS560_GDL, role: 'p', weight: 1 },
    ],
    dependencies: [],
  },
  {
    id: 'svc-0008',
    name: 'METRO-E-GDL-SOUTH',
    description: 'Metro Ethernet service — GDL South cluster',
    service_type: 'metro-e',
    status: 'degraded',
    created_at: OLDER(85),
    updated_at: OLDER(1),
    members: [
      { id: 'sm-015', device_id: DEV.ASR920_3, role: 'access', weight: 1 },
    ],
    dependencies: ['svc-0007'],
  },
];

// ─── Assurance ────────────────────────────────────────────────────────────────

export const DEMO_ASSURANCE_SERVICES = [
  { service_id: 'svc-0001', name: 'VPLS-ATT-CDMX-Ring',    score: 97, health_state: 'healthy' },
  { service_id: 'svc-0002', name: 'L3VPN-CORP-BACKBONE',   score: 72, health_state: 'degraded' },
  { service_id: 'svc-0003', name: 'MPLS-CORE-TRANSPORT',   score: 55, health_state: 'impaired' },
  { service_id: 'svc-0004', name: 'METRO-E-CDMX-NORTH',    score: 100, health_state: 'healthy' },
  { service_id: 'svc-0005', name: '4G-PGW-CDMX',           score: 83, health_state: 'degraded' },
  { service_id: 'svc-0006', name: '4G-PGW-GDL',            score: 96, health_state: 'healthy' },
  { service_id: 'svc-0007', name: 'VPLS-ATT-GDL-Ring',     score: 99, health_state: 'healthy' },
  { service_id: 'svc-0008', name: 'METRO-E-GDL-SOUTH',     score: 61, health_state: 'impaired' },
];

export const DEMO_SERVICE_ALERTS: unknown[] = [];

// ─── Topology ────────────────────────────────────────────────────────────────

export const DEMO_TOPOLOGY = {
  nodes: [
    { id: DEV.NCS55_CDMX,  label: 'ncs55a1-cdmx-core-01',   role: 'core',        vendor: 'Cisco', model: 'NCS-55A1-24Q6H-SS', status: 'reachable'   },
    { id: DEV.NCS55_GDL,   label: 'ncs55a1-gdl-core-01',    role: 'core',        vendor: 'Cisco', model: 'NCS-55A1-24Q6H-SS', status: 'reachable'   },
    { id: DEV.NCS55_MTY,   label: 'ncs55a1-mty-core-01',    role: 'core',        vendor: 'Cisco', model: 'NCS-55A1-24Q6H-SS', status: 'degraded'    },
    { id: DEV.NCS560_CDMX, label: 'ncs560-cdmx-agg-01',     role: 'aggregation', vendor: 'Cisco', model: 'NCS-560-4',         status: 'reachable'   },
    { id: DEV.NCS560_GDL,  label: 'ncs560-gdl-agg-01',      role: 'aggregation', vendor: 'Cisco', model: 'NCS-560-4',         status: 'reachable'   },
    { id: DEV.ASR9010_1,   label: 'asr9010-cdmx-pe-01',     role: 'pe',          vendor: 'Cisco', model: 'ASR-9010',          status: 'reachable'   },
    { id: DEV.ASR9010_2,   label: 'asr9010-cdmx-pe-02',     role: 'pe',          vendor: 'Cisco', model: 'ASR-9010',          status: 'reachable'   },
    { id: DEV.ASR9010_3,   label: 'asr9010-gdl-pe-01',      role: 'pe',          vendor: 'Cisco', model: 'ASR-9010',          status: 'unreachable' },
    { id: DEV.ASR920_1,    label: 'asr920-cdmx-acc-01',     role: 'access',      vendor: 'Cisco', model: 'ASR-920-24SZ-M',   status: 'reachable'   },
    { id: DEV.ASR920_2,    label: 'asr920-cdmx-acc-02',     role: 'access',      vendor: 'Cisco', model: 'ASR-920-24SZ-M',   status: 'reachable'   },
    { id: DEV.ASR920_3,    label: 'asr920-gdl-acc-01',      role: 'access',      vendor: 'Cisco', model: 'ASR-920-12CZ-A',   status: 'degraded'    },
    { id: DEV.ASR920_4,    label: 'asr920-mty-acc-01',      role: 'access',      vendor: 'Cisco', model: 'ASR-920-24SZ-M',   status: 'reachable'   },
    { id: DEV.ASR5K_1,     label: 'asr5000-cdmx-mobile-01', role: 'mobile-gw',   vendor: 'Cisco', model: 'ASR-5000',          status: 'reachable'   },
    { id: DEV.ASR5K_2,     label: 'asr5000-gdl-mobile-01',  role: 'mobile-gw',   vendor: 'Cisco', model: 'ASR-5000',          status: 'reachable'   },
    { id: DEV.ASR5K_3,     label: 'asr5000-mty-mobile-01',  role: 'mobile-gw',   vendor: 'Cisco', model: 'ASR-5000',          status: 'reachable'   },
  ],
  links: [
    // Core mesh
    { id: 'lnk-001', source: DEV.NCS55_CDMX, target: DEV.NCS55_GDL,  bandwidth_gbps: 100, utilization: 0.61, state: 'up' },
    { id: 'lnk-002', source: DEV.NCS55_CDMX, target: DEV.NCS55_MTY,  bandwidth_gbps: 100, utilization: 0.45, state: 'up' },
    { id: 'lnk-003', source: DEV.NCS55_GDL,  target: DEV.NCS55_MTY,  bandwidth_gbps: 100, utilization: 0.38, state: 'up' },
    // Core to aggregation
    { id: 'lnk-004', source: DEV.NCS55_CDMX, target: DEV.NCS560_CDMX, bandwidth_gbps: 40, utilization: 0.72, state: 'up' },
    { id: 'lnk-005', source: DEV.NCS55_GDL,  target: DEV.NCS560_GDL,  bandwidth_gbps: 40, utilization: 0.33, state: 'up' },
    // Core to PE
    { id: 'lnk-006', source: DEV.NCS55_CDMX, target: DEV.ASR9010_1, bandwidth_gbps: 10, utilization: 0.55, state: 'up' },
    { id: 'lnk-007', source: DEV.NCS55_CDMX, target: DEV.ASR9010_2, bandwidth_gbps: 10, utilization: 0.48, state: 'up' },
    { id: 'lnk-008', source: DEV.NCS55_GDL,  target: DEV.ASR9010_3, bandwidth_gbps: 10, utilization: 0.0,  state: 'down' },
    // Agg to access
    { id: 'lnk-009', source: DEV.NCS560_CDMX, target: DEV.ASR920_1, bandwidth_gbps: 1, utilization: 0.28, state: 'up' },
    { id: 'lnk-010', source: DEV.NCS560_CDMX, target: DEV.ASR920_2, bandwidth_gbps: 1, utilization: 0.31, state: 'up' },
    { id: 'lnk-011', source: DEV.NCS560_GDL,  target: DEV.ASR920_3, bandwidth_gbps: 1, utilization: 0.0,  state: 'down' },
    { id: 'lnk-012', source: DEV.NCS55_MTY,   target: DEV.ASR920_4, bandwidth_gbps: 1, utilization: 0.19, state: 'up' },
    // Mobile GW
    { id: 'lnk-013', source: DEV.NCS55_CDMX, target: DEV.ASR5K_1,  bandwidth_gbps: 10, utilization: 0.84, state: 'up' },
    { id: 'lnk-014', source: DEV.NCS55_GDL,  target: DEV.ASR5K_2,  bandwidth_gbps: 10, utilization: 0.56, state: 'up' },
    { id: 'lnk-015', source: DEV.NCS55_MTY,  target: DEV.ASR5K_3,  bandwidth_gbps: 10, utilization: 0.41, state: 'up' },
  ],
};
