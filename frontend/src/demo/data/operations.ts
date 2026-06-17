import { DEV, DEMO_DEVICES } from './devices';

// ─── Telemetry ────────────────────────────────────────────────────────────────

export const DEMO_TELEMETRY_HEALTH = {
  collectors: 3,
  enabled_collectors: 2,
  subscriptions: 8,
  enabled_subscriptions: 6,
};

const AGO = (s: number) => new Date(Date.now() - s * 1000).toISOString();

export const DEMO_TELEMETRY_COLLECTORS = [
  {
    id: 'col-001', name: 'gNMI-NCS-CDMX', collector_type: 'gnmi',
    endpoint: 'gnmi://10.10.1.1:57400', enabled: true, status: 'active',
    last_seen_at: AGO(45),
  },
  {
    id: 'col-002', name: 'gNMI-NCS-GDL', collector_type: 'gnmi',
    endpoint: 'gnmi://10.10.2.1:57400', enabled: true, status: 'active',
    last_seen_at: AGO(90),
  },
  {
    id: 'col-003', name: 'SNMP-Legacy-Poller', collector_type: 'snmp',
    endpoint: null, enabled: false, status: 'disabled',
    last_seen_at: null,
  },
];

const SENSOR_PATHS_RAW = [
  '/platform/components/component/cpu/utilization/state/instant',
  '/platform/components/component/memory/state/used',
  '/interfaces/interface/state/counters/in-octets',
  '/interfaces/interface/state/counters/out-octets',
  '/interfaces/interface/state/oper-status',
  'Cisco-IOS-XR-ncs5500-coherent-node-oper:coherent-nodes/coherent-node/coherent-port/rx-dbm',
  '/platform/components/component/state/temperature/instant',
  '/mpls/lsps/constrained-path/tunnels/tunnel/state/counters/bytes',
];

export const DEMO_TELEMETRY_SUBSCRIPTIONS = SENSOR_PATHS_RAW.map((path, i) => ({
  id: `sub-${String(i + 1).padStart(3, '0')}`,
  name: path.split('/').pop() ?? `sub-${i}`,
  path,
  collector_id: i < 4 ? 'col-001' : 'col-002',
  device_id: null,
  sample_interval_ms: [10000, 30000, 60000][i % 3],
  mode: 'stream',
  enabled: i < 6,
  status: i < 6 ? 'active' : 'disabled',
  last_sample_at: i < 6 ? AGO((i + 1) * 30) : null,
}));

export const DEMO_TELEMETRY_SENSOR_PATHS = [
  { id: 'sp-001', vendor: 'cisco', platform_family: 'NCS 5500', path: SENSOR_PATHS_RAW[0], metric_name: 'cpu_5min', kpi_type: 'cpu_5min', unit: '%', object_type: 'device', enabled: true },
  { id: 'sp-002', vendor: 'cisco', platform_family: 'NCS 5500', path: SENSOR_PATHS_RAW[1], metric_name: 'mem_used', kpi_type: 'mem_used', unit: 'bytes', object_type: 'device', enabled: true },
  { id: 'sp-003', vendor: 'cisco', platform_family: null, path: SENSOR_PATHS_RAW[2], metric_name: 'if_in_octets', kpi_type: 'if_in_octets', unit: 'octets', object_type: 'interface', enabled: true },
  { id: 'sp-004', vendor: 'cisco', platform_family: null, path: SENSOR_PATHS_RAW[3], metric_name: 'if_out_octets', kpi_type: 'if_out_octets', unit: 'octets', object_type: 'interface', enabled: true },
  { id: 'sp-005', vendor: 'cisco', platform_family: 'NCS 5500', path: SENSOR_PATHS_RAW[5], metric_name: 'optical_rx_dbm', kpi_type: 'optical_rx_dbm', unit: 'dBm', object_type: 'interface', enabled: true },
  { id: 'sp-006', vendor: 'cisco', platform_family: null, path: SENSOR_PATHS_RAW[6], metric_name: 'chassis_temp', kpi_type: 'chassis_temp', unit: 'C', object_type: 'device', enabled: false },
];

// ─── Commands ─────────────────────────────────────────────────────────────────

export const DEMO_COMMANDS = [
  { id: 'cmd-001', name: 'Show Version', cli_command: 'show version', output_path: '/tmp/show_version.txt', device_id: null },
  { id: 'cmd-002', name: 'Show Interfaces Summary', cli_command: 'show interfaces summary', output_path: '/tmp/show_intf.txt', device_id: null },
  { id: 'cmd-003', name: 'Show Environment All', cli_command: 'show environment all', output_path: '/tmp/show_env.txt', device_id: null },
  { id: 'cmd-004', name: 'Show BGP Summary', cli_command: 'show bgp summary', output_path: '/tmp/show_bgp.txt', device_id: null },
  { id: 'cmd-005', name: 'Show MPLS Forwarding', cli_command: 'show mpls forwarding', output_path: '/tmp/show_mpls.txt', device_id: null },
  { id: 'cmd-006', name: 'SSD Smart Monitor', cli_command: 'admin show smart-monitor', output_path: '/tmp/show_ssd.txt', device_id: null },
];

// ─── IOS Versions ─────────────────────────────────────────────────────────────

const EOL_VERSIONS = new Set(['7.6.2', '21.26.1']);
const EOS_VERSIONS = new Set(['7.6.2']);

export const DEMO_IOS_EOL_REPORT = DEMO_DEVICES.map((d) => ({
  device_id: d.id,
  device_name: d.name,
  version: d.software_version,
  is_eol: EOL_VERSIONS.has(d.software_version),
  is_eos: EOS_VERSIONS.has(d.software_version),
  eol_date: EOL_VERSIONS.has(d.software_version) ? '2025-03-31' : null,
  eos_date: EOS_VERSIONS.has(d.software_version) ? '2024-09-30' : null,
}));

export function getDemoIOSVersions(deviceId: string): Array<{ id: string; version: string; detected_at: string }> {
  const device = DEMO_DEVICES.find((d) => d.id === deviceId);
  if (!device) return [];
  return [{ id: `iosv-${deviceId}-1`, version: device.software_version, detected_at: device.updated_at }];
}

// ─── Monitoring Policies ──────────────────────────────────────────────────────

const NEXT_RUN = (m: number) => new Date(Date.now() + m * 60000).toISOString();

export const DEMO_MONITORING_POLICIES = [
  {
    id: 'pol-001', name: 'Device Health — All Devices',
    description: 'CPU, memory, uptime, and reachability polling for all managed devices.',
    policy_type: 'device_health', enabled: true, interval_seconds: 300,
    target_all_devices: true, device_ids: [], metric_oids: [], thresholds: {},
    last_run_at: AGO(300), next_run_at: NEXT_RUN(0), last_status: 'ok', last_error: null,
  },
  {
    id: 'pol-002', name: 'Interface Health — Core Routers',
    description: 'Interface counters, errors, and operational state for NCS55A1 and NCS560.',
    policy_type: 'interface_health', enabled: true, interval_seconds: 60,
    target_all_devices: false,
    device_ids: [DEV.NCS55_CDMX, DEV.NCS55_GDL, DEV.NCS55_MTY, DEV.NCS560_CDMX, DEV.NCS560_GDL],
    metric_oids: [], thresholds: {},
    last_run_at: AGO(60), next_run_at: NEXT_RUN(0), last_status: 'ok', last_error: null,
  },
  {
    id: 'pol-003', name: 'Optical SFP — Access Layer',
    description: 'Optical transceiver Rx/Tx power and temperature for ASR920 access routers.',
    policy_type: 'optical_sfp', enabled: true, interval_seconds: 900,
    target_all_devices: false,
    device_ids: [DEV.ASR920_1, DEV.ASR920_2, DEV.ASR920_3, DEV.ASR920_4],
    metric_oids: [], thresholds: {},
    last_run_at: AGO(900), next_run_at: NEXT_RUN(0), last_status: 'warning', last_error: null,
  },
  {
    id: 'pol-004', name: 'MPLS Link Performance — PE Routers',
    description: 'MPLS TE tunnel and LSP utilization counters for ASR9010 PE routers.',
    policy_type: 'mpls_link_performance', enabled: true, interval_seconds: 300,
    target_all_devices: false,
    device_ids: [DEV.ASR9010_1, DEV.ASR9010_2, DEV.ASR9010_3],
    metric_oids: [], thresholds: {},
    last_run_at: AGO(300), next_run_at: NEXT_RUN(0), last_status: 'ok', last_error: null,
  },
  {
    id: 'pol-005', name: 'Syslog Monitor',
    description: 'Capture syslog events from all managed devices and map to NMS alarms.',
    policy_type: 'syslog', enabled: false, interval_seconds: 60,
    target_all_devices: true, device_ids: [], metric_oids: [], thresholds: {},
    last_run_at: null, next_run_at: null, last_status: null, last_error: null,
  },
  {
    id: 'pol-006', name: 'SSD Temperature — NCS55A1',
    description: 'Smart Monitor SSD temperature for NCS55A1 line cards via custom MIB OID.',
    policy_type: 'custom_mib', enabled: true, interval_seconds: 3600,
    target_all_devices: false,
    device_ids: [DEV.NCS55_CDMX, DEV.NCS55_GDL, DEV.NCS55_MTY],
    metric_oids: [{ name: 'ssdTemp', oid: '1.3.6.1.4.1.9.9.99.1.1.1.3', unit: 'C' }],
    thresholds: { ssdTemp: { warning: 50, critical: 65 } },
    last_run_at: AGO(3600), next_run_at: NEXT_RUN(0), last_status: 'ok', last_error: null,
  },
];

export const DEMO_MONITORING_PRESETS = [
  { name: 'Device Health', policy_type: 'device_health', interval_seconds: 300, description: 'Poll CPU, memory, uptime, and reachability for all devices.' },
  { name: 'Interface Health', policy_type: 'interface_health', interval_seconds: 60, description: 'Poll interface counters, errors, and operational state.' },
  { name: 'Optical SFP', policy_type: 'optical_sfp', interval_seconds: 900, description: 'Poll optical transceiver Rx/Tx power and temperature.' },
  { name: 'MPLS Link Performance', policy_type: 'mpls_link_performance', interval_seconds: 300, description: 'Poll MPLS TE tunnel and LSP utilization.' },
  { name: 'Syslog Monitoring', policy_type: 'syslog', interval_seconds: 60, description: 'Capture syslog events and map them to NMS alarms.' },
];

// ─── Per-device inventory ─────────────────────────────────────────────────────

export function getDemoDeviceInventory(deviceId: string) {
  const device = DEMO_DEVICES.find((d) => d.id === deviceId);
  if (!device) return null;
  // Deterministic serial: last 4 hex digits of UUID
  const suffix = deviceId.replace(/-/g, '').slice(-4).toUpperCase();
  const daysSeed = parseInt(suffix, 16) % 180 + 30;
  const isXR = device.os_type === 'IOS XR';
  return {
    serial: `FOC27${suffix}P1A9`,
    serial_number: `FOC27${suffix}P1A9`,
    model: device.model,
    hardware_model: device.model,
    firmware: device.software_version,
    firmware_version: device.software_version,
    ports: isXR ? 24 : 48,
    port_count: isXR ? 24 : 48,
    cpu_cores: 4,
    memory_total: 32768,
    memory_free: isXR ? 12288 : 20480,
    uptime: `${daysSeed}d 4h`,
    uptime_seconds: daysSeed * 86400 + 14400,
  };
}
