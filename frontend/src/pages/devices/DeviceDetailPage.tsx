import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, LayoutDashboard, Network, RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Button, Card, StatCard, Spinner, EmptyState, PageHeader } from '../../components/ui';
import { ChassisView } from '../inventory/chassis/ChassisView';
import { DeviceStatusBadge } from './components/DeviceStatusBadge';
import { DeviceTagList } from './components/DeviceTagList';

interface Device {
  id: string;
  name: string;
  ip_address: string;
  vendor: string;
  model: string;
  os_type: string;
  device_type: string;
  location: string;
  status: string;
  tags: string[];
}

interface InventoryItem {
  serial: string;
  model: string;
  firmware: string;
  ports: number;
  cpu_cores: number;
  memory_total: number;
  memory_free: number;
  uptime: string;
}

interface IOSVersion {
  id: string;
  version: string;
  detected_at: string;
}

interface InterfaceRow {
  if_index: number;
  descr?: string | null;
  type?: number | null;
  speed?: number | null;
  admin_status?: number | null;
  oper_status?: number | null;
  in_octets?: number | null;
  out_octets?: number | null;
  in_errors?: number | null;
  out_errors?: number | null;
  alias?: string | null;
  phys_address?: string | null;
}

type Tab = 'overview' | 'chassis' | 'inventory' | 'interfaces' | 'ios' | 'kpis';

export function DeviceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [pollMessage, setPollMessage] = useState('');

  const { data: device, isLoading } = useQuery<Device>({
    queryKey: ['device', id],
    queryFn: () => api.get(`/devices/${id}`).then((r) => r.data),
    enabled: Boolean(id),
  });

  const { data: inventory } = useQuery<InventoryItem[]>({
    queryKey: ['device-inventory', id],
    queryFn: () => api.get(`/devices/${id}/inventory`).then((r) => r.data),
    enabled: activeTab === 'inventory' && Boolean(id),
  });

  const { data: iosVersions } = useQuery<IOSVersion[]>({
    queryKey: ['ios-versions', id],
    queryFn: () => api.get(`/ios/devices/${id}/versions`).then((r) => r.data),
    enabled: activeTab === 'ios' && Boolean(id),
  });

  const interfacesQuery = useQuery<InterfaceRow[]>({
    queryKey: ['device-interfaces', id],
    queryFn: () => api.get(`/devices/${id}/interfaces`).then((r) => r.data),
    enabled: activeTab === 'interfaces' && Boolean(id),
    retry: 1,
  });

  const pollMutation = useMutation({
    mutationFn: () => api.post(`/devices/${id}/poll`),
    onSuccess: () => {
      setPollMessage('Poll started successfully.');
      queryClient.invalidateQueries({ queryKey: ['device', id] });
      setTimeout(() => setPollMessage(''), 3000);
    },
    onError: (err) => {
      console.error('Poll failed', err);
      alert('Failed to poll device');
    },
  });

  if (isLoading) return <Spinner />;
  if (!device) return <p className="p-6 text-red-500">Device not found.</p>;
  const supportsChassisView = isSupportedChassisDevice(device);

  const TABS: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    ...(supportsChassisView ? [{ key: 'chassis' as Tab, label: 'Chassis' }] : []),
    { key: 'inventory', label: 'Inventory' },
    { key: 'interfaces', label: 'Interfaces' },
    { key: 'ios', label: 'IOS Versions' },
    { key: 'kpis', label: 'Recent KPIs' },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate('/devices')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <PageHeader
          title={device.name}
          subtitle={device.ip_address}
          actions={
            <div className="flex items-center gap-2">
              {pollMessage && <span className="text-green-600 text-sm">{pollMessage}</span>}
              <Button variant="ghost" size="sm" onClick={() => navigate(`/devices/${id}/dashboard`)}>
                <LayoutDashboard className="w-4 h-4 mr-1" />
                Dashboard
              </Button>
              <Button onClick={() => pollMutation.mutate()} disabled={pollMutation.isPending}>
                <RefreshCw className={`w-4 h-4 mr-1 ${pollMutation.isPending ? 'animate-spin' : ''}`} />
                Poll now
              </Button>
            </div>
          }
        />
      </div>

      {/* Header info */}
      <div className="flex flex-wrap gap-3 items-center">
        <DeviceStatusBadge status={device.status} />
        <span className="text-sm text-gray-500">{device.vendor} {device.model}</span>
        <span className="text-sm text-gray-500">{device.os_type}</span>
        {device.location && <span className="text-sm text-gray-400">{device.location}</span>}
        <DeviceTagList tags={device.tags} />
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === 'overview' && (
        <Card className="p-4 space-y-3">
          <h3 className="font-semibold text-gray-700">System information</h3>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            <dt className="text-gray-500">Type</dt><dd>{device.device_type}</dd>
            <dt className="text-gray-500">Vendor</dt><dd>{device.vendor || '—'}</dd>
            <dt className="text-gray-500">Model</dt><dd>{device.model || '—'}</dd>
            <dt className="text-gray-500">OS</dt><dd>{device.os_type}</dd>
            <dt className="text-gray-500">Location</dt><dd>{device.location || '—'}</dd>
            <dt className="text-gray-500">Status</dt><dd><DeviceStatusBadge status={device.status} /></dd>
          </dl>
        </Card>
      )}

      {activeTab === 'chassis' && supportsChassisView && (
        <ChassisView deviceName={device.name} deviceId={device.id} />
      )}

      {activeTab === 'inventory' && (
        <div className="space-y-4">
          {!inventory && <Spinner />}
          {inventory && inventory.length === 0 && (
            <EmptyState title="No inventory" description="No inventory data is available for this device." />
          )}
          {inventory && inventory.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {['Serial', 'Model', 'Firmware', 'Ports', 'CPU Cores', 'Mem Total', 'Free Mem', 'Uptime'].map((h) => (
                      <th key={h} className="px-4 py-2 text-left text-gray-600 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {inventory.map((item, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono">{item.serial}</td>
                      <td className="px-4 py-2">{item.model}</td>
                      <td className="px-4 py-2">{item.firmware}</td>
                      <td className="px-4 py-2">{item.ports}</td>
                      <td className="px-4 py-2">{item.cpu_cores}</td>
                      <td className="px-4 py-2">{item.memory_total} MB</td>
                      <td className="px-4 py-2">{item.memory_free} MB</td>
                      <td className="px-4 py-2">{item.uptime}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'interfaces' && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 font-semibold text-gray-700 dark:text-gray-100">
                <Network className="h-4 w-4" /> Live IF-MIB interfaces
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400">Fetched on demand through SNMP using the device credential profile.</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => interfacesQuery.refetch()} disabled={interfacesQuery.isFetching}>
              <RefreshCw className={`w-4 h-4 mr-1 ${interfacesQuery.isFetching ? 'animate-spin' : ''}`} /> Refresh
            </Button>
          </div>

          {interfacesQuery.isLoading && <Spinner />}
          {interfacesQuery.isError && (
            <EmptyState
              title="Interface fetch failed"
              description="Check that the device has a valid SNMP credential and is reachable from the backend."
            />
          )}
          {interfacesQuery.data && interfacesQuery.data.length === 0 && (
            <EmptyState title="No interfaces returned" description="The device responded, but no IF-MIB rows were returned." />
          )}
          {interfacesQuery.data && interfacesQuery.data.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {['Index', 'Description', 'Alias', 'Admin', 'Oper', 'Speed', 'Errors', 'MAC'].map((h) => (
                      <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {interfacesQuery.data.map((iface) => (
                    <tr key={iface.if_index} className="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                      <td className="px-3 py-2 font-mono text-gray-700 dark:text-gray-200">{iface.if_index}</td>
                      <td className="px-3 py-2 text-gray-900 dark:text-white">{iface.descr || '—'}</td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{iface.alias || '—'}</td>
                      <td className="px-3 py-2"><StatusPill value={iface.admin_status} /></td>
                      <td className="px-3 py-2"><StatusPill value={iface.oper_status} /></td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{formatSpeed(iface.speed)}</td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{formatErrors(iface)}</td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500 dark:text-gray-400">{iface.phys_address || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}

      {activeTab === 'ios' && (
        <div>
          {!iosVersions && <Spinner />}
          {iosVersions && iosVersions.length === 0 && (
            <EmptyState title="No versions" description="No IOS versions have been detected for this device." />
          )}
          {iosVersions && iosVersions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-gray-600">Version</th>
                    <th className="px-4 py-2 text-left text-gray-600">Detected at</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {iosVersions.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono">{v.version}</td>
                      <td className="px-4 py-2">{new Date(v.detected_at).toLocaleString('en-US')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'kpis' && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard label="Status" value={device.status} />
          <StatCard label="OS" value={device.os_type} />
          <StatCard label="Vendor" value={device.vendor || '—'} />
          <StatCard label="Model" value={device.model || '—'} />
        </div>
      )}
    </div>
  );
}

function isSupportedChassisDevice(device: Device): boolean {
  const searchable = [
    device.vendor,
    device.model,
    device.device_type,
    device.os_type,
    device.name,
  ].join(' ');
  return /cisco/i.test(searchable) && (/(?:asr[\s-]?(903|920|9006)|ncs[\s-]?55a1)/i.test(searchable));
}

function StatusPill({ value }: { value?: number | null }) {
  const label = value === 1 ? 'up' : value === 2 ? 'down' : value == null ? 'unknown' : String(value);
  const classes = value === 1
    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
    : value === 2
      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
      : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300';
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>{label}</span>;
}

function formatSpeed(speed?: number | null) {
  if (!speed) return '—';
  if (speed >= 1_000_000_000) return `${(speed / 1_000_000_000).toFixed(1)} Gbps`;
  if (speed >= 1_000_000) return `${Math.round(speed / 1_000_000)} Mbps`;
  if (speed >= 1_000) return `${Math.round(speed / 1_000)} Kbps`;
  return `${speed} bps`;
}

function formatErrors(iface: InterfaceRow) {
  const total = (iface.in_errors ?? 0) + (iface.out_errors ?? 0);
  return total ? `${total} (${iface.in_errors ?? 0}/${iface.out_errors ?? 0})` : '0';
}
