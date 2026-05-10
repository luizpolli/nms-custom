import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { Button, Card, StatCard, Spinner, EmptyState, PageHeader } from '../../components/ui';
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

type Tab = 'overview' | 'inventory' | 'interfaces' | 'ios' | 'kpis';

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

  const pollMutation = useMutation({
    mutationFn: () => api.post(`/devices/${id}/poll`),
    onSuccess: () => {
      setPollMessage('Consulta iniciada correctamente.');
      queryClient.invalidateQueries({ queryKey: ['device', id] });
      setTimeout(() => setPollMessage(''), 3000);
    },
    onError: (err) => {
      console.error('Poll failed', err);
      alert('Error al consultar el dispositivo');
    },
  });

  const TABS: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Resumen' },
    { key: 'inventory', label: 'Inventario' },
    { key: 'interfaces', label: 'Interfaces' },
    { key: 'ios', label: 'Versiones IOS' },
    { key: 'kpis', label: 'KPIs recientes' },
  ];

  if (isLoading) return <Spinner />;
  if (!device) return <p className="p-6 text-red-500">Dispositivo no encontrado.</p>;

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
              <Button onClick={() => pollMutation.mutate()} disabled={pollMutation.isPending}>
                <RefreshCw className={`w-4 h-4 mr-1 ${pollMutation.isPending ? 'animate-spin' : ''}`} />
                Consultar ahora
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
          <h3 className="font-semibold text-gray-700">Información del sistema</h3>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            <dt className="text-gray-500">Tipo</dt><dd>{device.device_type}</dd>
            <dt className="text-gray-500">Fabricante</dt><dd>{device.vendor || '—'}</dd>
            <dt className="text-gray-500">Modelo</dt><dd>{device.model || '—'}</dd>
            <dt className="text-gray-500">OS</dt><dd>{device.os_type}</dd>
            <dt className="text-gray-500">Ubicación</dt><dd>{device.location || '—'}</dd>
            <dt className="text-gray-500">Estado</dt><dd><DeviceStatusBadge status={device.status} /></dd>
          </dl>
        </Card>
      )}

      {activeTab === 'inventory' && (
        <div>
          {!inventory && <Spinner />}
          {inventory && inventory.length === 0 && (
            <EmptyState title="Sin inventario" description="No hay datos de inventario para este dispositivo." />
          )}
          {inventory && inventory.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {['Serial', 'Modelo', 'Firmware', 'Puertos', 'CPU Cores', 'Mem Total', 'Mem Libre', 'Uptime'].map((h) => (
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
        <Card className="p-6 text-center text-gray-500">
          {/* TODO: Backend does not expose interfaces endpoint yet. Implement when GET /devices/{id}/interfaces is available. */}
          <p className="text-sm">Las interfaces aún no están disponibles.</p>
          <p className="text-xs text-gray-400 mt-1">Pendiente: implementar cuando el backend exponga <code>GET /devices/{'{'}{id}{'}'}/interfaces</code>.</p>
        </Card>
      )}

      {activeTab === 'ios' && (
        <div>
          {!iosVersions && <Spinner />}
          {iosVersions && iosVersions.length === 0 && (
            <EmptyState title="Sin versiones" description="No se han detectado versiones IOS para este dispositivo." />
          )}
          {iosVersions && iosVersions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-gray-600">Versión</th>
                    <th className="px-4 py-2 text-left text-gray-600">Detectada el</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {iosVersions.map((v) => (
                    <tr key={v.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono">{v.version}</td>
                      <td className="px-4 py-2">{new Date(v.detected_at).toLocaleString('es-MX')}</td>
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
          <StatCard label="Estado" value={device.status} />
          <StatCard label="OS" value={device.os_type} />
          <StatCard label="Fabricante" value={device.vendor || '—'} />
          <StatCard label="Modelo" value={device.model || '—'} />
        </div>
      )}
    </div>
  );
}
