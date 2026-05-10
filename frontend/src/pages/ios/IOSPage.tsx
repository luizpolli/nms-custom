import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { PageHeader, Button, Select, Spinner, EmptyState, Badge } from '../../components/ui';

interface Device {
  id: string;
  name: string;
}

interface IOSVersion {
  id: string;
  version: string;
  detected_at: string;
}

interface EOLEntry {
  device_id: string;
  device_name: string;
  version: string;
  is_eol: boolean;
  is_eos: boolean;
  eol_date?: string;
  eos_date?: string;
}

type Tab = 'by-device' | 'eol-report';

export function IOSPage() {
  const [activeTab, setActiveTab] = useState<Tab>('by-device');
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [detectMessage, setDetectMessage] = useState('');

  const { data: devicesData } = useQuery<{ items: Device[] }>({
    queryKey: ['devices-select'],
    queryFn: () => api.get('/devices', { params: { limit: 200 } }).then((r) => r.data),
  });
  const devices: Device[] = Array.isArray(devicesData) ? devicesData : (devicesData?.items ?? []);

  const { data: iosVersions, isLoading: loadingVersions } = useQuery<IOSVersion[]>({
    queryKey: ['ios-versions', selectedDeviceId],
    queryFn: () => api.get(`/ios/devices/${selectedDeviceId}/versions`).then((r) => r.data),
    enabled: Boolean(selectedDeviceId) && activeTab === 'by-device',
  });

  const { data: eolReport, isLoading: loadingEol } = useQuery<EOLEntry[]>({
    queryKey: ['ios-eol-report'],
    queryFn: () => api.get('/ios/eol-report').then((r) => r.data),
    enabled: activeTab === 'eol-report',
  });

  const detectMutation = useMutation({
    mutationFn: (deviceId: string) => api.post(`/ios/devices/${deviceId}/detect`),
    onSuccess: () => {
      setDetectMessage('Detección iniciada.');
      setTimeout(() => setDetectMessage(''), 3000);
    },
    onError: (err) => {
      console.error('Detect failed', err);
      alert('Error al detectar versión IOS');
    },
  });

  const TABS = [
    { key: 'by-device' as Tab, label: 'Por dispositivo' },
    { key: 'eol-report' as Tab, label: 'Reporte EOL' },
  ];

  return (
    <div className="p-6 space-y-6">
      <PageHeader title="Versiones IOS" subtitle="Gestión y seguimiento de versiones de software" />

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

      {/* By Device */}
      {activeTab === 'by-device' && (
        <div className="space-y-4">
          <div className="flex gap-3 items-end">
            <Select
              label="Seleccionar dispositivo"
              value={selectedDeviceId}
              onChange={(e) => setSelectedDeviceId(e.target.value)}
              options={[
                { value: '', label: '— Selecciona un dispositivo —' },
                ...devices.map((d) => ({ value: d.id, label: d.name })),
              ]}
              className="w-72"
            />
            {selectedDeviceId && (
              <div className="flex items-center gap-2">
                {detectMessage && <span className="text-green-600 text-sm">{detectMessage}</span>}
                <Button
                  onClick={() => detectMutation.mutate(selectedDeviceId)}
                  disabled={detectMutation.isPending}
                >
                  {detectMutation.isPending ? 'Detectando...' : 'Detectar ahora'}
                </Button>
              </div>
            )}
          </div>

          {!selectedDeviceId && (
            <EmptyState title="Sin selección" description="Selecciona un dispositivo para ver sus versiones IOS." />
          )}

          {selectedDeviceId && loadingVersions && <Spinner />}

          {selectedDeviceId && iosVersions && iosVersions.length === 0 && (
            <EmptyState title="Sin versiones" description="No se han detectado versiones IOS para este dispositivo." />
          )}

          {iosVersions && iosVersions.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Versión</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Detectada el</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
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

      {/* EOL Report */}
      {activeTab === 'eol-report' && (
        <div className="space-y-4">
          {loadingEol && <Spinner />}
          {eolReport && eolReport.length === 0 && (
            <EmptyState title="Sin datos" description="No hay reporte EOL disponible." />
          )}
          {eolReport && eolReport.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full text-sm divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {['Dispositivo', 'Versión', 'EOL', 'EOS', 'Fecha EOL', 'Fecha EOS'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 bg-white">
                  {eolReport.map((entry, i) => (
                    <tr
                      key={i}
                      className={`hover:bg-gray-50 ${entry.is_eol || entry.is_eos ? 'bg-red-50' : ''}`}
                    >
                      <td className="px-4 py-2 font-medium">{entry.device_name}</td>
                      <td className="px-4 py-2 font-mono">{entry.version}</td>
                      <td className="px-4 py-2">
                        <Badge variant={entry.is_eol ? 'danger' : 'success'}>{entry.is_eol ? 'Sí' : 'No'}</Badge>
                      </td>
                      <td className="px-4 py-2">
                        <Badge variant={entry.is_eos ? 'danger' : 'success'}>{entry.is_eos ? 'Sí' : 'No'}</Badge>
                      </td>
                      <td className="px-4 py-2">{entry.eol_date ? new Date(entry.eol_date).toLocaleDateString('es-MX') : '—'}</td>
                      <td className="px-4 py-2">{entry.eos_date ? new Date(entry.eos_date).toLocaleDateString('es-MX') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
