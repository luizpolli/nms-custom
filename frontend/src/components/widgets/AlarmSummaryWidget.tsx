import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Badge } from '../ui/Badge';
import type { AlarmSummary } from '../../lib/types';

function useAlarmSummary() {
  return useQuery({
    queryKey: ['alarms', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<AlarmSummary>('/alarms/summary');
      return data;
    },
    refetchInterval: 30_000,
  });
}

type SeverityKey = 'critical' | 'major' | 'minor' | 'warning' | 'info';

const SEVERITIES: { key: SeverityKey; label: string }[] = [
  { key: 'critical', label: 'Critical' },
  { key: 'major', label: 'Major' },
  { key: 'minor', label: 'Minor' },
  { key: 'warning', label: 'Warning' },
  { key: 'info', label: 'Info' },
];

function getCount(data: AlarmSummary | undefined, key: SeverityKey): number {
  if (!data) return 0;
  return data[key] ?? data.by_severity?.[key] ?? 0;
}

export function AlarmSummaryWidget() {
  const { data, isLoading, error } = useAlarmSummary();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error || !data) return <div className="p-4 text-sm text-red-500">Failed to load alarm summary.</div>;

  const total = SEVERITIES.reduce((sum, s) => sum + getCount(data, s.key), 0);

  return (
    <div className="space-y-1 p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Total active</span>
        <span className="text-2xl font-bold text-gray-800 dark:text-gray-100">{total}</span>
      </div>
      {SEVERITIES.map(({ key, label }) => (
        <div key={key} className="flex items-center justify-between text-sm">
          <span className="text-gray-700 dark:text-gray-300">{label}</span>
          <Badge variant={key as never}>{getCount(data, key)}</Badge>
        </div>
      ))}
    </div>
  );
}
