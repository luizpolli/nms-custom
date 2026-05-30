import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import type { Alarm } from '../../lib/types';

function useRecentAlarms() {
  return useQuery({
    queryKey: ['alarms', 'recent-widget'],
    queryFn: async () => {
      const { data } = await api.get<Alarm[]>('/alarms', { params: { limit: 10 } });
      return data;
    },
    refetchInterval: 20_000,
  });
}

function timeAgo(value?: string) {
  if (!value) return '—';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function RecentAlarmsWidget() {
  const { data, isLoading, error } = useRecentAlarms();
  const navigate = useNavigate();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error) return <div className="p-4 text-sm text-red-500">Failed to load recent alarms.</div>;
  if (!data?.length) return <EmptyState message="No alarms recorded yet" />;

  return (
    <ul className="divide-y divide-gray-100 dark:divide-gray-800 overflow-auto">
      {data.map((alarm) => (
        <li key={alarm.id}>
          <button
            type="button"
            onClick={() => navigate('/alarms')}
            className="grid w-full grid-cols-[auto,minmax(0,1fr),auto] items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50"
          >
            <Badge variant={alarm.severity as never}>{alarm.severity}</Badge>
            <div className="min-w-0">
              <div className="truncate font-medium text-gray-800 dark:text-gray-100">
                {alarm.source_host ?? alarm.source ?? 'unknown'}
              </div>
              <div className="truncate text-xs text-gray-500 dark:text-gray-400">{alarm.message}</div>
            </div>
            <span className="whitespace-nowrap text-xs text-gray-400">
              {timeAgo(alarm.last_seen ?? alarm.raised_at)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
