// ─── Device ──────────────────────────────────────────────────────────────────

export type DeviceStatus = 'reachable' | 'unreachable' | 'unknown' | 'polling';
export type DevicePlatform = 'ncs55a1' | 'ncs560' | 'asr920' | 'asr9010' | 'asr5k' | string;

export interface Device {
  id: string;
  name: string;
  ip_address: string;
  platform: DevicePlatform;
  status: DeviceStatus;
  credential_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface DeviceCreate {
  name: string;
  ip_address: string;
  platform: DevicePlatform;
  credential_id?: string;
  tags?: string[];
}

export interface DevicePatch {
  name?: string;
  ip_address?: string;
  platform?: DevicePlatform;
  credential_id?: string | null;
  tags?: string[];
}

// ─── Credential ──────────────────────────────────────────────────────────────

export type CredentialType = 'snmpv2' | 'snmpv3' | 'ssh' | 'netconf';

export interface Credential {
  id: string;
  name: string;
  type: CredentialType;
  username?: string;
  has_secret: boolean;
  snmp_community?: string;
  snmp_version?: string;
  created_at: string;
  updated_at: string;
}

export interface CredentialCreate {
  name: string;
  type: CredentialType;
  username?: string;
  secret?: string;
  snmp_community?: string;
  snmp_version?: string;
}

// ─── KPI / Performance ───────────────────────────────────────────────────────

export type KpiType = 'cpu' | 'memory' | 'interface_in' | 'interface_out' | 'latency' | string;

export interface KPI {
  id: string;
  device_id: string;
  kpi_type: KpiType;
  value: number;
  unit: string;
  timestamp: string;
  interface_name?: string;
}

export interface KPIAggregate {
  device_id: string;
  kpi_type: KpiType;
  avg: number;
  min: number;
  max: number;
  count: number;
  unit: string;
  since: string;
  until: string;
}

export interface PerformanceSummary {
  device_id: string;
  device_name: string;
  cpu_avg?: number;
  memory_avg?: number;
  last_polled_at?: string;
  top_devices?: Array<{
    device_id: string;
    name: string;
    cpu_5min?: number;
  }>;
}

// ─── MIB ─────────────────────────────────────────────────────────────────────

export interface MIB {
  id: string;
  name: string;
  filename: string;
  oid_prefix?: string;
  uploaded_at: string;
}

// ─── Discovery ───────────────────────────────────────────────────────────────

export interface DiscoveryScanRequest {
  cidr: string;
  communities: string[];
}

export type DiscoveredDeviceStatus = 'new' | 'existing' | 'unreachable';

export interface DiscoveredDevice {
  ip_address: string;
  sysDescr?: string;
  sysName?: string;
  status: DiscoveredDeviceStatus;
}

export interface DiscoveryScanResult {
  cidr: string;
  scanned: number;
  discovered: DiscoveredDevice[];
  started_at: string;
  finished_at: string;
}

// ─── Command ─────────────────────────────────────────────────────────────────

export interface Command {
  id: string;
  name: string;
  cli: string;
  description?: string;
  created_at: string;
}

export interface CommandResult {
  device_id: string;
  command_id?: string;
  cli: string;
  output: string;
  exit_code: number;
  executed_at: string;
}

export interface AdHocCommandRequest {
  device_id: string;
  cli: string;
}

// ─── IOS Version ─────────────────────────────────────────────────────────────

export interface IOSVersion {
  id: string;
  device_id: string;
  version: string;
  platform: string;
  detected_at: string;
  is_eol: boolean;
  eol_date?: string;
}

export interface EOLReport {
  generated_at: string;
  devices: Array<{
    device_id: string;
    device_name: string;
    ip_address: string;
    version: string;
    eol_date?: string;
    days_to_eol?: number;
  }>;
}

// ─── Alarm ───────────────────────────────────────────────────────────────────

export type AlarmSeverity = 'critical' | 'major' | 'minor' | 'warning' | 'info' | 'clear';
export type AlarmState = 'active' | 'acknowledged' | 'cleared';

export interface Alarm {
  id: string;
  device_id: string;
  device_name?: string;
  severity: AlarmSeverity;
  state: AlarmState;
  message: string;
  source?: string;
  source_host?: string;
  oid?: string;
  event_type?: string;
  raised_at: string;
  last_seen?: string;
  acknowledged_at?: string;
  acknowledged_by?: string;
  cleared_at?: string;
}

export interface AlarmSummary {
  total: number;
  active: number;
  acknowledged: number;
  cleared: number;
  by_severity: Record<AlarmSeverity, number>;
  critical?: number;
  major?: number;
  minor?: number;
  warning?: number;
  info?: number;
}

export interface AlarmWsMessage {
  type: 'hb' | 'alarm';
  ts?: string;
  alarm?: Alarm;
}

// ─── Topology ────────────────────────────────────────────────────────────────

export interface TopologyNode {
  id: string;
  label: string;
  role?: string;
  position?: { x: number; y: number };
}

export interface TopologyLink {
  source: string;
  target: string;
  source_iface?: string;
  target_iface?: string;
}

export interface TopologyGraph {
  nodes: TopologyNode[];
  links: TopologyLink[];
}

// ─── Inventory ───────────────────────────────────────────────────────────────

export interface InventoryItem {
  id: string;
  device_id: string;
  component_type: string;
  name: string;
  description?: string;
  serial_number?: string;
  model?: string;
  firmware?: string;
  discovered_at: string;
}

// ─── Health ──────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string;
  app: string;
}

// ─── Reports ─────────────────────────────────────────────────────────────────

export interface ReportDefinition {
  id: string;
  name: string;
  description?: string;
  parameters?: Record<string, string>;
}

export interface ReportGenerateRequest {
  report_id: string;
  parameters?: Record<string, string>;
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}
