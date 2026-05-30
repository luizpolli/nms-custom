import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { EmptyState } from '../ui/EmptyState';
import type { PerformanceSummary } from '../../lib/types';

function usePerformanceSummary() {
  return useQuery({
    queryKey: ['performance', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<PerformanceSummary>('/performance/summary');
      return data;
    },
    refetchInterval: 30_000,
  });
}

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  const color =
    value >= 90
      ? 'bg-red-500'
      : value >= 70
        ? 'bg-amber-500'
        : 'bg-emerald-500';
  return (
    <div className="h-1.5 w-full rounded-full bg-gray-200 dark:bg-gray-700">
      <div
        className={`h-1.5 rounded-full ${color} transition-all`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function TopCPUWidget() {
  const { data, isLoading, error } = usePerformanceSummary();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error) return <div className="p-4 text-sm text-red-500">Failed to load performance data.</div>;

  const devices = data?.top_devices ?? [];
  if (!devices.length) return <EmptyState message="No KPI data available" />;

  const maxCpu = Math.max(...devices.map((d) => d.cpu_5min ?? 0), 1);

  return (
    <ul className="divide-y divide-gray-100 overflow-auto dark:divide-gray-800">
      {devices.slice(0, 10).map((d) => {
        const cpu = d.cpu_5min ?? 0;
        return (
          <li key={d.device_id} className="flex flex-col gap-1 px-3 py-2.5">
            <div className="flex items-center justify-between text-sm">
              <span className="truncate text-gray-800 dark:text-gray-100">{d.name}</span>
              <span className="ml-2 shrink-0 text-xs font-semibold text-gray-600 dark:text-gray-400">
                {cpu.toFixed(1)}%
              </span>
            </div>
            <Bar value={cpu} max={maxCpu} />
          </li>
        );
      })}
    </ul>
  );
}
