import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isDemoEnabled } from '../../demo/index';
import { DEMO_DEVICES, EXAMPLE_DEVICE_BASE } from '../../demo/data/devices';
import {
  Cable,
  Cpu,
  HardDrive,
  Layers3,
  Package,
  RefreshCw,
  Router,
  ShieldCheck,
  Thermometer,
} from 'lucide-react';
import { api } from '../../lib/api';
import { PageHeader, Button, Spinner, EmptyState, Card, Badge, StatCard, Table } from '../../components/ui';
import { ChassisView } from './chassis/ChassisView';

interface Device {
  id: string;
  name: string;
  vendor?: string;
  model?: string;
  device_type?: string;
  os_type?: string;
}

interface InventoryItem {
  serial?: string;
  serial_number?: string;
  model?: string;
  hardware_model?: string;
  firmware?: string;
  firmware_version?: string;
  ports?: number;
  port_count?: number;
  cpu_cores?: number;
  memory_total?: number;
  memory_free?: number;
  uptime?: string;
  uptime_seconds?: number;
}

interface DeviceInventoryRow extends InventoryItem {
  device_name: string;
  device_id: string;
}

type InventoryMode = 'live' | 'example';

const exampleDevice = {
  ...EXAMPLE_DEVICE_BASE,
  environment: [
    { label: 'CPU', value: '18%', icon: <Cpu className="h-5 w-5" />, tone: 'success' },
    { label: 'Memory', value: '41%', icon: <HardDrive className="h-5 w-5" />, tone: 'default' },
    { label: 'Temperature', value: '34 C', icon: <Thermometer className="h-5 w-5" />, tone: 'success' },
    { label: 'Power feeds', value: '2/2', icon: <ShieldCheck className="h-5 w-5" />, tone: 'success' },
  ],
};

function modelToChassisProfile(model: string): string | undefined {
  const m = model.toUpperCase();
  const map: [string, string][] = [
    ['55A1-24Q6H', 'ncs55a1-24q6h'], ['55A1-48Q6H', 'ncs55a1-48q6h'],
    ['55A1-24H', 'ncs55a1-24h'],     ['55A1', 'ncs55a1'],
    ['NCS-560', 'ncs560'],           ['9010', 'asr9010'],
    ['9006', 'asr9006'],             ['920-24SZ', 'asr920-24sz'],
    ['920-12CZ', 'asr920-12cz'],     ['920-12SZ', 'asr920-12sz'],
    ['920', 'asr920'],
  ];
  return map.find(([k]) => m.includes(k))?.[1];
}

const exampleChassisProfiles = [
  { id: 'asr903', label: 'ASR 903', deviceName: exampleDevice.name, dataUrl: '/chassis-assets/asr903/normalized.json' },
  { id: 'asr920', label: 'ASR 920', deviceName: 'MEX-EDGE-ASR920-01', dataUrl: '/chassis-assets/asr920/normalized.json' },
  { id: 'asr920-12cz', label: 'ASR 920 12CZ', deviceName: 'MEX-EDGE-ASR920-12CZ', dataUrl: '/chassis-assets/asr920-12cz/normalized.json' },
  { id: 'asr920-12sz', label: 'ASR 920 12SZ', deviceName: 'MEX-EDGE-ASR920-12SZ', dataUrl: '/chassis-assets/asr920-12sz/normalized.json' },
  { id: 'asr920-12sz-im', label: 'ASR 920 12SZ-IM', deviceName: 'MEX-EDGE-ASR920-12SZIM', dataUrl: '/chassis-assets/asr920-12sz-im/normalized.json' },
  { id: 'asr920-24sz', label: 'ASR 920 24SZ', deviceName: 'MEX-EDGE-ASR920-24SZ', dataUrl: '/chassis-assets/asr920-24sz/normalized.json' },
  { id: 'asr9006', label: 'ASR 9006', deviceName: 'MEX-CORE-ASR9K-01', dataUrl: '/chassis-assets/asr9006/normalized.json' },
  { id: 'asr9010', label: 'ASR 9010', deviceName: 'MEX-CORE-ASR9010-01', dataUrl: '/chassis-assets/asr9010/normalized.json' },
  { id: 'asr9901', label: 'ASR 9901', deviceName: 'MEX-CORE-ASR9901-01', dataUrl: '/chassis-assets/asr9901/normalized.json' },
  { id: 'asr9902', label: 'ASR 9902', deviceName: 'MEX-CORE-ASR9902-01', dataUrl: '/chassis-assets/asr9902/normalized.json' },
  { id: 'asr9903', label: 'ASR 9903', deviceName: 'MEX-CORE-ASR9903-01', dataUrl: '/chassis-assets/asr9903/normalized.json' },
  { id: 'ncs55a1', label: 'NCS55A1-36H', deviceName: 'MEX-CORE-NCS55A1-01', dataUrl: '/chassis-assets/ncs55a1/normalized.json' },
  { id: 'ncs55a1-48q6h', label: 'NCS55A1-48Q6H', deviceName: 'MEX-CORE-NCS55A1-48Q6H', dataUrl: '/chassis-assets/ncs55a1-48q6h/normalized.json' },
  { id: 'ncs55a1-24q6h', label: 'NCS55A1-24Q6H', deviceName: 'MEX-CORE-NCS55A1-24Q6H', dataUrl: '/chassis-assets/ncs55a1-24q6h/normalized.json' },
  { id: 'ncs55a1-24h', label: 'NCS55A1-24H', deviceName: 'MEX-CORE-NCS55A1-24H', dataUrl: '/chassis-assets/ncs55a1-24h/normalized.json' },
  { id: 'ncs5504', label: 'NCS5504', deviceName: 'MEX-CORE-NCS5504-01', dataUrl: '/chassis-assets/ncs5504/normalized.json' },
  { id: 'ncs5516', label: 'NCS5516', deviceName: 'MEX-CORE-NCS5516-01', dataUrl: '/chassis-assets/ncs5516/normalized.json' },
  { id: 'ncs560', label: 'NCS560', deviceName: 'MEX-CORE-NCS560-01', dataUrl: '/chassis-assets/ncs560/normalized.json' },
  { id: 'ncs560-4', label: 'NCS560-4', deviceName: 'MEX-AGG-NCS560-4-01', dataUrl: '/chassis-assets/ncs560-4/normalized.json' },
  { id: 'ncs560-enh', label: 'NCS560 Enhanced', deviceName: 'MEX-AGG-NCS560-ENH-01', dataUrl: '/chassis-assets/ncs560-enh/normalized.json' },
  { id: 'ncs540', label: 'NCS540', deviceName: 'MEX-EDGE-NCS540-01', dataUrl: '/chassis-assets/ncs540/normalized.json' },
  { id: 'ncs540-12z16g', label: 'NCS540X-12Z16G', deviceName: 'MEX-EDGE-NCS540X-12Z16G', dataUrl: '/chassis-assets/ncs540-12z16g/normalized.json' },
  { id: 'ncs540-16z4', label: 'NCS540X-16Z4', deviceName: 'MEX-EDGE-NCS540X-16Z4', dataUrl: '/chassis-assets/ncs540-16z4/normalized.json' },
  { id: 'ncs540-acc-sys', label: 'NCS540-ACC-SYS', deviceName: 'MEX-EDGE-NCS540-ACC-SYS', dataUrl: '/chassis-assets/ncs540-acc-sys/normalized.json' },
  { id: 'ncs540-12z20g', label: 'NCS540-12Z20G', deviceName: 'MEX-EDGE-NCS540-12Z20G', dataUrl: '/chassis-assets/ncs540-12z20g/normalized.json' },
  { id: 'ncs540-28z4c', label: 'NCS540-28Z4C', deviceName: 'MEX-EDGE-NCS540-28Z4C', dataUrl: '/chassis-assets/ncs540-28z4c/normalized.json' },
  { id: 'ncs540-fh-agg', label: 'NCS540-FH-AGG', deviceName: 'MEX-EDGE-NCS540-FH-AGG', dataUrl: '/chassis-assets/ncs540-fh-agg/normalized.json' },
  { id: 'ncs540-fh-csr', label: 'NCS540-FH-CSR', deviceName: 'MEX-EDGE-NCS540-FH-CSR', dataUrl: '/chassis-assets/ncs540-fh-csr/normalized.json' },
  { id: 'ncs540x-4z14g2q', label: 'NCS540X-4Z14G2Q', deviceName: 'MEX-EDGE-NCS540X-4Z14G2Q', dataUrl: '/chassis-assets/ncs540x-4z14g2q/normalized.json' },
  { id: 'ncs5501', label: 'NCS5501', deviceName: 'MEX-CORE-NCS5501-01', dataUrl: '/chassis-assets/ncs5501/normalized.json' },
  { id: 'ncs5502', label: 'NCS5502', deviceName: 'MEX-CORE-NCS5502-01', dataUrl: '/chassis-assets/ncs5502/normalized.json' },
  { id: 'ncs5508', label: 'NCS5508', deviceName: 'MEX-CORE-NCS5508-01', dataUrl: '/chassis-assets/ncs5508/normalized.json' },
];

async function fetchAllInventory(): Promise<DeviceInventoryRow[]> {
  const devicesResp = await api.get<{ items?: Device[] } | Device[]>('/devices', { params: { limit: 200 } });
  const rawDevices = Array.isArray(devicesResp.data) ? devicesResp.data : devicesResp.data.items ?? [];

  const results = await Promise.allSettled(
    rawDevices.map((d: Device) =>
      api
        .get<InventoryItem[] | InventoryItem | null>(`/devices/${d.id}/inventory`)
        .then((r) => {
          const rows = Array.isArray(r.data) ? r.data : r.data ? [r.data] : [];
          return rows.map((item) => ({
            ...item,
            device_name: d.name,
            device_id: d.id,
          }));
        })
    )
  );

  return results
    .filter((r): r is PromiseFulfilledResult<DeviceInventoryRow[]> => r.status === 'fulfilled')
    .flatMap((r) => r.value);
}

function formatUptime(row: InventoryItem): string {
  if (row.uptime) return row.uptime;
  if (!row.uptime_seconds) return '-';
  const days = Math.floor(row.uptime_seconds / 86400);
  const hours = Math.floor((row.uptime_seconds % 86400) / 3600);
  return `${days}d ${hours}h`;
}

function rowSerial(row: InventoryItem): string {
  return row.serial ?? row.serial_number ?? '-';
}

function rowModel(row: InventoryItem): string {
  return row.model ?? row.hardware_model ?? '-';
}

function rowFirmware(row: InventoryItem): string {
  return row.firmware ?? row.firmware_version ?? '-';
}

function rowPorts(row: InventoryItem): number | string {
  return row.ports ?? row.port_count ?? '-';
}

const DEMO_ROLE_LABELS: Record<string, string> = {
  core: 'Core backbone router', aggregation: 'Aggregation router',
  access: 'Access / cell-site router', pe: 'Provider edge router', 'mobile-gw': 'Mobile gateway',
};

function ExampleInventoryModel({ pinnedDeviceId }: { pinnedDeviceId?: string }) {
  const demoDevice = pinnedDeviceId ? DEMO_DEVICES.find((d) => d.id === pinnedDeviceId) : undefined;
  const profileId = demoDevice ? (modelToChassisProfile(demoDevice.model) ?? 'asr903') : 'asr903';
  const defaultProfile = exampleChassisProfiles.find((p) => p.id === profileId) ?? exampleChassisProfiles[0];
  const [selectedChassisProfile, setSelectedChassisProfile] = useState(defaultProfile);
  const device = demoDevice ? {
    ...exampleDevice,
    name: demoDevice.name,
    managementIp: demoDevice.ip_address,
    platform: demoDevice.model.replace(/^([A-Z]+)-/, '$1 '),
    os: `${demoDevice.os_type} ${demoDevice.software_version}`,
    site: demoDevice.location,
    role: DEMO_ROLE_LABELS[demoDevice.role] ?? demoDevice.role,
    serial: `FOX${demoDevice.name.split('').reduce((a, c) => (a + c.charCodeAt(0)) % 10000, 0).toString().padStart(4, '0')}`,
  } : exampleDevice;
  const totalPorts = 32;
  const activeOptics = device.optics.filter((optic) => optic.status === 'ok').length;

  return (
    <div className="space-y-6">
      <Card className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Router className="h-5 w-5 text-cisco-blue" />
              <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{device.name}</h2>
              <Badge variant="success">{device.collectionStatus}</Badge>
              <Badge variant="default">Example</Badge>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {device.role} - {device.site}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4 lg:text-right">
            <Metric label="Mgmt IP" value={device.managementIp} />
            <Metric label="Platform" value={device.platform} />
            <Metric label="Serial" value={device.serial} mono />
            <Metric label="Last collection" value={device.lastCollection} />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-4">
          <StatCard title="Modules" value={device.modules.length} icon={<Layers3 className="h-5 w-5" />} />
          <StatCard title="Ports" value={totalPorts} icon={<Cable className="h-5 w-5" />} />
          <StatCard title="Optics OK" value={`${activeOptics}/${device.optics.length}`} icon={<Package className="h-5 w-5" />} tone="success" />
          <StatCard title="Uptime" value={device.uptime} icon={<RefreshCw className="h-5 w-5" />} />
        </div>
      </Card>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {exampleChassisProfiles.map((profile) => (
            <Button
              key={profile.id}
              type="button"
              size="sm"
              variant={selectedChassisProfile.id === profile.id ? 'primary' : 'outline'}
              onClick={() => setSelectedChassisProfile(profile)}
            >
              {profile.label}
            </Button>
          ))}
        </div>
        <ChassisView deviceName={selectedChassisProfile.deviceName} dataUrl={selectedChassisProfile.dataUrl} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.8fr)]">
        <Card className="space-y-4">
          <SectionTitle title="Hardware hierarchy" subtitle="Chassis, route processors, line cards, fans, and power modules." />
          <Table
            columns={[
              { key: 'slot', header: 'Slot' },
              { key: 'type', header: 'Type' },
              { key: 'part', header: 'Part number' },
              { key: 'serial', header: 'Serial' },
              { key: 'ports', header: 'Ports' },
              { key: 'firmware', header: 'FW' },
              { key: 'status', header: 'Status', render: (value) => <Badge variant={value === 'OK' || value === 'Standby' ? 'success' : 'warning'}>{String(value)}</Badge> },
            ]}
            data={device.modules}
          />
        </Card>

        <Card className="space-y-4">
          <SectionTitle title="Software & lifecycle" subtitle="Operating image, packages, license, and lifecycle state." />
          <div className="grid gap-3 text-sm">
            <MetricLine label="Vendor" value={device.vendor} />
            <MetricLine label="OS" value={device.os} />
            <MetricLine label="License" value={device.license} />
            <MetricLine label="Lifecycle" value={device.lifecycle} />
          </div>
          <div className="space-y-2">
            {device.software.map((pkg) => (
              <div key={pkg.name} className="flex items-center justify-between gap-3 rounded-md border border-gray-200 px-3 py-2 text-sm dark:border-gray-700">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">{pkg.name}</p>
                  <p className="font-mono text-xs text-gray-500 dark:text-gray-400">{pkg.version}</p>
                </div>
                <Badge variant="success">{pkg.state}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <Card className="space-y-4">
          <SectionTitle title="Optics and transceivers" subtitle="Per-port optics with part number, serial, wavelength, and optical power." />
          <Table
            columns={[
              { key: 'interface', header: 'Interface' },
              { key: 'type', header: 'Type' },
              { key: 'part', header: 'Part' },
              { key: 'serial', header: 'Serial' },
              { key: 'wavelength', header: 'Wave' },
              { key: 'rxPower', header: 'RX' },
              { key: 'txPower', header: 'TX' },
              { key: 'status', header: 'Status', render: (value) => <Badge variant={value === 'ok' ? 'success' : 'warning'}>{value === 'ok' ? 'OK' : 'Check'}</Badge> },
            ]}
            data={device.optics}
          />
        </Card>

        <Card className="space-y-4">
          <SectionTitle title="Environment snapshot" subtitle="Current operational health from the latest collection." />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
            {device.environment.map((item) => (
              <StatCard key={item.label} title={item.label} value={item.value} icon={item.icon} tone={item.tone} />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`mt-0.5 font-medium text-gray-900 dark:text-gray-100 ${mono ? 'font-mono text-xs' : ''}`}>{value}</p>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-2 last:border-0 dark:border-gray-800">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right font-medium text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{subtitle}</p>
    </div>
  );
}

function isSupportedChassisDevice(device: Device): boolean {
  const searchable = [device.vendor, device.model, device.device_type, device.os_type, device.name]
    .filter(Boolean)
    .join(' ');
  return /cisco/i.test(searchable) && (/(?:asr[\s-]?(903|920|9006)|ncs[\s-]?(55a1|560|540)|n540)/i.test(searchable));
}

async function fetchDevices(): Promise<Device[]> {
  const resp = await api.get<{ items?: Device[] } | Device[]>('/devices', { params: { limit: 500 } });
  return Array.isArray(resp.data) ? resp.data : resp.data.items ?? [];
}

export function InventoryPage() {
  const [searchParams] = useSearchParams();
  const [mode, setMode] = useState<InventoryMode>(() => isDemoEnabled() ? 'example' : 'live');
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');
  const [pinnedDeviceId, setPinnedDeviceId] = useState<string | undefined>(undefined);

  // When navigated from Devices page with a device_id param, pre-select the device
  useEffect(() => {
    const deviceId = searchParams.get('device_id');
    if (!deviceId) return;
    if (isDemoEnabled()) {
      setMode('example');
      setPinnedDeviceId(deviceId);
    } else {
      setMode('live');
      setSelectedDeviceId(deviceId);
    }
  }, [searchParams]);

  const { data, isLoading, isError, refetch, isFetching } = useQuery<DeviceInventoryRow[]>({
    queryKey: ['all-inventory'],
    queryFn: fetchAllInventory,
  });
  const devicesQuery = useQuery<Device[]>({
    queryKey: ['inventory-devices'],
    queryFn: fetchDevices,
    enabled: mode === 'live',
  });

  const demoActive = isDemoEnabled();
  const rows = data ?? [];
  const chassisCapableDevices = (devicesQuery.data ?? []).filter(isSupportedChassisDevice);
  const selectedDevice = chassisCapableDevices.find((d) => d.id === selectedDeviceId);

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Inventory"
        subtitle={mode === 'example' ? 'Modeled device inventory example' : `${rows.length} inventory entries`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {demoActive && (
              <div className="inline-flex rounded-md border border-gray-300 bg-white p-1 dark:border-gray-700 dark:bg-gray-900">
                <button
                  type="button"
                  onClick={() => setMode('example')}
                  className={`rounded px-3 py-1.5 text-sm font-medium ${mode === 'example' ? 'bg-cisco-blue text-white' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'}`}
                >
                  Example Model
                </button>
                <button
                  type="button"
                  onClick={() => setMode('live')}
                  className={`rounded px-3 py-1.5 text-sm font-medium ${mode === 'live' ? 'bg-cisco-blue text-white' : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'}`}
                >
                  Live Inventory
                </button>
              </div>
            )}
            <Button variant="ghost" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={`w-4 h-4 mr-1 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {mode === 'example' && <ExampleInventoryModel key={pinnedDeviceId ?? 'default'} pinnedDeviceId={pinnedDeviceId} />}

      {mode === 'live' && (
        <>
          {chassisCapableDevices.length > 0 && (
            <Card className="space-y-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Live chassis view</h3>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {chassisCapableDevices.length} device{chassisCapableDevices.length === 1 ? '' : 's'} with chassis profiles available.
                  </p>
                </div>
                <select
                  value={selectedDeviceId}
                  onChange={(e) => setSelectedDeviceId(e.target.value)}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                >
                  <option value="">Select a device…</option>
                  {chassisCapableDevices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} {d.model ? `· ${d.model}` : ''}
                    </option>
                  ))}
                </select>
              </div>
              {selectedDevice && (
                <ChassisView deviceName={selectedDevice.name} deviceId={selectedDevice.id} />
              )}
            </Card>
          )}

          {isLoading && <Spinner />}
          {isError && <p className="text-red-500">Failed to load inventory.</p>}
          {!isLoading && rows.length === 0 && (
            <EmptyState title="No inventory" description="No inventory data is available." />
          )}

          {rows.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full text-sm divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {[
                      'Device',
                      'Serial',
                      'Model',
                      'Firmware',
                      'Ports',
                      'CPU Cores',
                      'Total Mem (MB)',
                      'Free Mem (MB)',
                      'Uptime',
                    ].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider dark:text-gray-400">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-800 dark:bg-gray-900">
                  {rows.map((row, i) => (
                    <tr key={`${row.device_id}-${i}`} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-4 py-2 font-medium text-blue-700 dark:text-blue-300">{row.device_name}</td>
                      <td className="px-4 py-2 font-mono text-xs">{rowSerial(row)}</td>
                      <td className="px-4 py-2">{rowModel(row)}</td>
                      <td className="px-4 py-2 font-mono text-xs">{rowFirmware(row)}</td>
                      <td className="px-4 py-2 text-center">{rowPorts(row)}</td>
                      <td className="px-4 py-2 text-center">{row.cpu_cores ?? '-'}</td>
                      <td className="px-4 py-2 text-right">{row.memory_total ?? '-'}</td>
                      <td className="px-4 py-2 text-right">{row.memory_free ?? '-'}</td>
                      <td className="px-4 py-2">{formatUptime(row)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
