import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Badge } from '../ui/Badge';
import type { Device, DeviceStatus } from '../../lib/types';

function useDeviceStatus() {
  return useQuery({
    queryKey: ['devices', 'status-summary'],
    queryFn: async () => {
      const { data } = await api.get<Device[]>('/devices', { params: { limit: 1000 } });
      return data;
    },
    refetchInterval: 30_000,
  });
}

type StatusRow = { status: DeviceStatus; count: number; label: string; variant: string };

const STATUS_ORDER: DeviceStatus[] = ['reachable', 'unreachable', 'polling', 'unknown'];
const STATUS_META: Record<DeviceStatus, { label: string; variant: string }> = {
  reachable:   { label: 'Reachable',   variant: 'success' },
  unreachable: { label: 'Unreachable', variant: 'danger' },
  polling:     { label: 'Polling',     variant: 'info' },
  unknown:     { label: 'Unknown',     variant: 'neutral' },
};

export function DeviceStatusWidget() {
  const { data, isLoading, error } = useDeviceStatus();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error || !data) return <div className="p-4 text-sm text-red-500">Failed to load device status.</div>;

  const counts: Record<DeviceStatus, number> = { reachable: 0, unreachable: 0, polling: 0, unknown: 0 };
  data.forEach((d) => {
    const s = d.status in counts ? d.status : 'unknown';
    counts[s] += 1;
  });

  const rows: StatusRow[] = STATUS_ORDER.map((s) => ({
    status: s,
    count: counts[s],
    label: STATUS_META[s].label,
    variant: STATUS_META[s].variant,
  }));

  return (
    <div className="space-y-1 p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Total devices</span>
        <span className="text-2xl font-bold text-gray-800 dark:text-gray-100">{data.length}</span>
      </div>
      {rows.map(({ status, count, label, variant }) => (
        <div key={status} className="flex items-center justify-between text-sm">
          <span className="text-gray-700 dark:text-gray-300">{label}</span>
          <Badge variant={variant as never}>{count}</Badge>
        </div>
      ))}
    </div>
  );
}
