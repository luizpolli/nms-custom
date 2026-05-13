import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { DateRangeInput } from './DateRangeInput';

interface Device {
  id: string;
  hostname?: string;
  ip_address?: string;
}

export interface ReportParams {
  since?: string;
  until?: string;
  device_ids?: string[];
  device_id?: string;
}

interface Props {
  reportName: string;
  params: ReportParams;
  onChange: (p: ReportParams) => void;
}

function useDevices() {
  return useQuery<Device[]>({
    queryKey: ['devices-list'],
    queryFn: async () => {
      const res = await axios.get<Device[]>('/api/devices');
      return res.data;
    },
  });
}

function deviceLabel(d: Device) {
  return d.hostname ?? d.ip_address ?? d.id;
}

export function ReportParamsForm({ reportName, params, onChange }: Props) {
  const set = (patch: Partial<ReportParams>) => onChange({ ...params, ...patch });

  const { data: devices = [] } = useDevices();

  if (reportName === 'device_inventory') {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
        Este reporte no requiere parámetros adicionales.
      </p>
    );
  }

  if (reportName === 'kpi') {
    return (
      <div className="space-y-4">
        <DateRangeInput
          since={params.since ?? ''}
          until={params.until ?? ''}
          onSinceChange={(v) => set({ since: v })}
          onUntilChange={(v) => set({ until: v })}
        />
        <div>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
            Dispositivos (opcional)
          </label>
          <select
            multiple
            value={params.device_ids ?? []}
            onChange={(e) => {
              const selected = Array.from(e.target.selectedOptions).map((o) => o.value);
              set({ device_ids: selected });
            }}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px]"
          >
            {devices.map((d) => (
              <option key={d.id} value={d.id}>{deviceLabel(d)}</option>
            ))}
          </select>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Mantén Ctrl/Cmd para seleccionar varios</p>
        </div>
      </div>
    );
  }

  if (reportName === 'device_health') {
    return (
      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
          Dispositivo <span className="text-red-500">*</span>
        </label>
        <select
          value={params.device_id ?? ''}
          onChange={(e) => set({ device_id: e.target.value })}
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Seleccionar dispositivo...</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>{deviceLabel(d)}</option>
          ))}
        </select>
      </div>
    );
  }

  // alarms | executive_summary
  return (
    <DateRangeInput
      since={params.since ?? ''}
      until={params.until ?? ''}
      onSinceChange={(v) => set({ since: v })}
      onUntilChange={(v) => set({ until: v })}
    />
  );
}
