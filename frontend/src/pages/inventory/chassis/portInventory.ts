import type { ChassisComponent, ChassisComponentPort, ChassisViewModel } from './chassisTypes';

export type ManagedPort = ChassisComponentPort & {
  componentId: string;
  componentName: string;
  componentTypeId?: string;
};

export type ManagedInterface = {
  id: string;
  if_index?: number | null;
  name: string;
  description?: string | null;
  alias?: string | null;
  mac_address?: string | null;
  admin_status?: string | null;
  oper_status?: string | null;
  speed_bps?: number | null;
  interface_type?: string | null;
  role?: string | null;
};

export type PortInventoryRow = {
  id: string;
  kind: 'physical' | 'logical';
  name: string;
  source: string;
  componentName?: string;
  physicalIndex?: number | string | null;
  ifIndex?: number | null;
  adminStatus?: string | null;
  operStatus?: string | null;
  speedBps?: number | null;
};

export function collectManagedPorts(
  component: ChassisComponent | undefined,
  componentsById: Record<string, ChassisComponent>,
): ManagedPort[] {
  if (!component) return [];

  const ports: ManagedPort[] = component.ports.map((port) => ({
    ...port,
    componentId: component.id,
    componentName: component.displayName,
    componentTypeId: component.typeId,
  }));

  for (const childId of component.childIds) {
    ports.push(...collectManagedPorts(componentsById[childId], componentsById));
  }

  return ports.sort((a, b) => {
    const left = a.name ?? String(a.portId ?? a.id);
    const right = b.name ?? String(b.portId ?? b.id);
    return left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });
  });
}

export function normalizeInterfaceName(value?: string | number | null): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/^gigabitethernet/, 'gi')
    .replace(/^tengigabitethernet/, 'te')
    .replace(/^hundredgigabitethernet/, 'hu');
}

export function matchManagedInterface(port: ManagedPort | undefined, interfaces: ManagedInterface[]): ManagedInterface | undefined {
  if (!port) return undefined;
  const portName = normalizeInterfaceName(port.name);
  const portId = String(port.portId ?? port.id);

  return interfaces.find((iface) => {
    const names = [iface.name, iface.description, iface.alias].map(normalizeInterfaceName);
    return names.includes(portName) || String(iface.if_index ?? '') === portId;
  });
}

export type PortStatus = 'up' | 'down' | 'admin-down';

export type PortStatusInfo = {
  status: PortStatus;
  interfaceName: string;
  adminStatus?: string | null;
  operStatus?: string | null;
};

export function classifyPortStatus(
  adminStatus?: string | null,
  operStatus?: string | null,
): PortStatus | null {
  const admin = String(adminStatus ?? '').trim().toLowerCase();
  const oper = String(operStatus ?? '').trim().toLowerCase();
  if (admin === 'down') return 'admin-down';
  if (oper === 'up') return 'up';
  if (oper === 'down' || oper === 'lowerlayerdown' || oper === 'lower-layer-down' || oper === 'dormant') {
    return 'down';
  }
  return null;
}

export function buildPortStatusByComponentId(
  model: ChassisViewModel,
  interfaces: ManagedInterface[],
): Record<string, PortStatusInfo> {
  if (!interfaces.length) return {};

  const byNormalizedName = new Map<string, ManagedInterface>();
  for (const iface of interfaces) {
    for (const candidate of [iface.name, iface.description, iface.alias]) {
      const key = normalizeInterfaceName(candidate);
      if (key && !byNormalizedName.has(key)) byNormalizedName.set(key, iface);
    }
  }

  const result: Record<string, PortStatusInfo> = {};
  for (const component of Object.values(model.componentsById)) {
    const looksLikePort =
      component.type?.toLowerCase() === 'port' ||
      isPhysicalInterfaceName(component.name) ||
      isPhysicalInterfaceName(component.displayName);
    if (!looksLikePort) continue;

    let iface: ManagedInterface | undefined;
    for (const candidate of [component.name, component.displayName]) {
      const key = normalizeInterfaceName(candidate);
      if (key && byNormalizedName.has(key)) {
        iface = byNormalizedName.get(key);
        break;
      }
    }
    if (!iface) continue;

    const status = classifyPortStatus(iface.admin_status, iface.oper_status);
    if (!status) continue;
    result[component.id] = {
      status,
      interfaceName: iface.name,
      adminStatus: iface.admin_status,
      operStatus: iface.oper_status,
    };
  }
  return result;
}

export function isLogicalInterfaceName(name?: string | null): boolean {
  const value = String(name ?? '').trim();
  if (!value) return false;
  if (value.includes('.')) return true;
  return /^(?:BD|BDI|Bundle-Ether|Lo|Loopback|Nu|Null|Po|Port-channel|Tunnel|Vi|Virtual|Vlan)\d/i.test(value);
}

export function isPhysicalInterfaceName(name?: string | null): boolean {
  const value = String(name ?? '').trim();
  if (!value || isLogicalInterfaceName(value)) return false;
  return /^(?:Eth|Ethernet|Fa|FastEthernet|Fo|FortyGigE|Gi|GigabitEthernet|Hu|HundredGigE|MgmtEth|Te|TenGigE|TwentyFiveGigE)\d/i.test(value);
}

function collectPhysicalPortRows(model: ChassisViewModel): PortInventoryRow[] {
  const rows: PortInventoryRow[] = [];
  const seen = new Set<string>();

  for (const component of Object.values(model.componentsById)) {
    const componentName = component.displayName ?? component.name;
    if (component.type?.toLowerCase() === 'port') {
      const id = `component:${component.id}`;
      seen.add(id);
      rows.push({
        id,
        kind: 'physical',
        name: componentName,
        source: component.source?.type ?? 'chassis',
        componentName,
        physicalIndex: component.physicalIndex,
      });
    }

    for (const port of component.ports ?? []) {
      const portId = String(port.portId ?? port.id);
      const id = `port:${component.id}:${portId}`;
      if (seen.has(id)) continue;
      seen.add(id);
      rows.push({
        id,
        kind: 'physical',
        name: port.name ?? `Port ${portId}`,
        source: component.source?.type ?? 'chassis',
        componentName,
        physicalIndex: component.physicalIndex ?? port.portId,
      });
    }
  }

  return rows.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
}

export function buildPortInventoryRows(model: ChassisViewModel, interfaces: ManagedInterface[]): PortInventoryRow[] {
  const rows = collectPhysicalPortRows(model);
  const physicalNames = new Set(rows.map((row) => normalizeInterfaceName(row.name)).filter(Boolean));

  for (const iface of interfaces) {
    const normalizedName = normalizeInterfaceName(iface.name);
    const kind = isPhysicalInterfaceName(iface.name) ? 'physical' : 'logical';
    if (kind === 'physical' && physicalNames.has(normalizedName)) continue;
    rows.push({
      id: `interface:${iface.id}`,
      kind,
      name: iface.name,
      source: 'if-mib',
      ifIndex: iface.if_index,
      adminStatus: iface.admin_status,
      operStatus: iface.oper_status,
      speedBps: iface.speed_bps,
    });
  }

  return rows.sort((a, b) => {
    if (a.kind !== b.kind) return a.kind === 'physical' ? -1 : 1;
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
  });
}

export function formatSpeedBps(speed?: number | null) {
  if (!speed) return '-';
  if (speed >= 1_000_000_000) return `${(speed / 1_000_000_000).toFixed(1)} Gbps`;
  if (speed >= 1_000_000) return `${(speed / 1_000_000).toFixed(1)} Mbps`;
  if (speed >= 1_000) return `${(speed / 1_000).toFixed(1)} Kbps`;
  return `${speed} bps`;
}
