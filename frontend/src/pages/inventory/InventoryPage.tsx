import { useQuery } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import { PageHeader, Button, Spinner, EmptyState } from '../../components/ui';

interface Device {
  id: string;
  name: string;
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

interface DeviceInventoryRow extends InventoryItem {
  device_name: string;
  device_id: string;
}

async function fetchAllInventory(): Promise<DeviceInventoryRow[]> {
  const devicesResp = await api.get<{ items: Device[] }>('/devices', { params: { limit: 200 } });
  const devices = devicesResp.data.items ?? devicesResp.data;

  const results = await Promise.allSettled(
    (Array.isArray(devices) ? devices : []).map((d: Device) =>
      api
        .get<InventoryItem[]>(`/devices/${d.id}/inventory`)
        .then((r) =>
          (r.data ?? []).map((item) => ({
            ...item,
            device_name: d.name,
            device_id: d.id,
          }))
        )
    )
  );

  return results
    .filter((r): r is PromiseFulfilledResult<DeviceInventoryRow[]> => r.status === 'fulfilled')
    .flatMap((r) => r.value);
}

export function InventoryPage() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery<DeviceInventoryRow[]>({
    queryKey: ['all-inventory'],
    queryFn: fetchAllInventory,
  });

  const rows = data ?? [];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Inventario"
        subtitle={`${rows.length} entradas de inventario`}
        actions={
          <Button variant="ghost" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`w-4 h-4 mr-1 ${isFetching ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
        }
      />

      {isLoading && <Spinner />}
      {isError && <p className="text-red-500">Error al cargar inventario.</p>}
      {!isLoading && rows.length === 0 && (
        <EmptyState title="Sin inventario" description="No hay datos de inventario disponibles." />
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {[
                  'Dispositivo',
                  'Serial',
                  'Modelo',
                  'Firmware',
                  'Puertos',
                  'CPU Cores',
                  'Mem Total (MB)',
                  'Mem Libre (MB)',
                  'Uptime',
                ].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {rows.map((row, i) => (
                <tr key={`${row.device_id}-${i}`} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium text-blue-700">{row.device_name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.serial}</td>
                  <td className="px-4 py-2">{row.model}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.firmware}</td>
                  <td className="px-4 py-2 text-center">{row.ports}</td>
                  <td className="px-4 py-2 text-center">{row.cpu_cores}</td>
                  <td className="px-4 py-2 text-right">{row.memory_total}</td>
                  <td className="px-4 py-2 text-right">{row.memory_free}</td>
                  <td className="px-4 py-2">{row.uptime}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
