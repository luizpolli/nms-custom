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
  bucket?: string;
  consolidation?: string;
  top_n?: number;
  kpi_types?: string[];
  baseline_periods?: number;
  buckets?: string[];
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

const BUCKETS = ['raw', '5min', '15min', '1h', '1d', '1w'] as const;
const CONSOLIDATIONS = ['avg', 'min', 'max', 'p95', 'p99', 'last', 'sum'] as const;

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </div>
  );
}

function DevicesMultiSelect({
  devices,
  selected,
  onChange,
  label = 'Devices (optional)',
}: {
  devices: Device[];
  selected: string[];
  onChange: (ids: string[]) => void;
  label?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">{label}</label>
      <select
        multiple
        value={selected}
        onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}
        className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px]"
      >
        {devices.map((d) => (
          <option key={d.id} value={d.id}>{deviceLabel(d)}</option>
        ))}
      </select>
      <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Hold Ctrl/Cmd to select multiple items</p>
    </div>
  );
}

export function ReportParamsForm({ reportName, params, onChange }: Props) {
  const set = (patch: Partial<ReportParams>) => onChange({ ...params, ...patch });

  const { data: devices = [] } = useDevices();

  if (reportName === 'device_inventory' || reportName === 'monitoring_policies') {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 italic">
        This report does not require additional parameters.
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
        <div className="grid grid-cols-2 gap-3">
          <SelectField
            label="Bucket"
            value={params.bucket ?? 'raw'}
            options={BUCKETS}
            onChange={(v) => set({ bucket: v })}
          />
          <SelectField
            label="Consolidation"
            value={params.consolidation ?? 'avg'}
            options={CONSOLIDATIONS}
            onChange={(v) => set({ consolidation: v })}
          />
        </div>
        <DevicesMultiSelect
          devices={devices}
          selected={params.device_ids ?? []}
          onChange={(ids) => set({ device_ids: ids })}
        />
      </div>
    );
  }

  if (reportName === 'kpi_top_n') {
    return (
      <div className="space-y-4">
        <DateRangeInput
          since={params.since ?? ''}
          until={params.until ?? ''}
          onSinceChange={(v) => set({ since: v })}
          onUntilChange={(v) => set({ until: v })}
        />
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Top N</label>
            <input
              type="number"
              min={1}
              max={100}
              value={params.top_n ?? 10}
              onChange={(e) => set({ top_n: Number(e.target.value) })}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <SelectField
            label="Ranking statistic"
            value={params.consolidation ?? 'p95'}
            options={CONSOLIDATIONS}
            onChange={(v) => set({ consolidation: v })}
          />
        </div>
      </div>
    );
  }

  if (reportName === 'kpi_trends') {
    return (
      <div className="space-y-4">
        <DateRangeInput
          since={params.since ?? ''}
          until={params.until ?? ''}
          onSinceChange={(v) => set({ since: v })}
          onUntilChange={(v) => set({ until: v })}
        />
        <DevicesMultiSelect
          devices={devices}
          selected={params.device_ids ?? []}
          onChange={(ids) => set({ device_ids: ids })}
        />
        <p className="text-xs text-gray-400 dark:text-gray-500">
          Default buckets: 1h / 1d / 1w (Cricket-style trending view).
        </p>
      </div>
    );
  }

  if (reportName === 'baseline_comparison') {
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
            Baseline periods (prior windows)
          </label>
          <input
            type="number"
            min={1}
            max={12}
            value={params.baseline_periods ?? 4}
            onChange={(e) => set({ baseline_periods: Number(e.target.value) })}
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <DevicesMultiSelect
          devices={devices}
          selected={params.device_ids ?? []}
          onChange={(ids) => set({ device_ids: ids })}
        />
      </div>
    );
  }

  if (reportName === 'device_health') {
    return (
      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
          Device <span className="text-red-500">*</span>
        </label>
        <select
          value={params.device_id ?? ''}
          onChange={(e) => set({ device_id: e.target.value })}
          className="w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Select device...</option>
          {devices.map((d) => (
            <option key={d.id} value={d.id}>{deviceLabel(d)}</option>
          ))}
        </select>
      </div>
    );
  }

  // alarms | executive_summary | tca
  return (
    <DateRangeInput
      since={params.since ?? ''}
      until={params.until ?? ''}
      onSinceChange={(v) => set({ since: v })}
      onUntilChange={(v) => set({ until: v })}
    />
  );
}
