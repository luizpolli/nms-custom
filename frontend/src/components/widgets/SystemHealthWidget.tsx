import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';

interface WorkerStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'offline' | string;
  last_seen?: string;
  details?: string;
}

interface SystemHealthResponse {
  status: string;
  workers?: WorkerStatus[];
  receivers?: WorkerStatus[];
  uptime_seconds?: number;
}

function useSystemHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: async () => {
      const { data } = await api.get<SystemHealthResponse>('/health/workers');
      return data;
    },
    refetchInterval: 30_000,
    retry: 1,
  });
}

function statusDot(status: string) {
  if (status === 'healthy') return 'bg-green-500';
  if (status === 'degraded') return 'bg-amber-500';
  return 'bg-red-500';
}

function formatUptime(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 24) return `${Math.floor(h / 24)}d ${h % 24}h`;
  return `${h}h ${m}m`;
}

export function SystemHealthWidget() {
  const { data, isLoading, error } = useSystemHealth();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error) return <div className="p-4 text-sm text-red-500">System health data unavailable.</div>;

  const all: WorkerStatus[] = [...(data?.workers ?? []), ...(data?.receivers ?? [])];

  return (
    <div className="p-3 space-y-2">
      {/* Overall status banner */}
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${statusDot(data?.status ?? 'unknown')}`} />
        <span className="text-sm font-medium text-gray-800 dark:text-gray-100 capitalize">
          {data?.status ?? 'Unknown'}
        </span>
        {data?.uptime_seconds != null && (
          <span className="ml-auto text-xs text-gray-500 dark:text-gray-400">
            up {formatUptime(data.uptime_seconds)}
          </span>
        )}
      </div>

      {all.length > 0 && (
        <ul className="space-y-1.5 pt-1 border-t border-gray-100 dark:border-gray-800">
          {all.map((w, i) => (
            <li key={`${w.name}-${i}`} className="flex items-center gap-2 text-xs">
              <span className={`h-2 w-2 rounded-full shrink-0 ${statusDot(w.status)}`} />
              <span className="flex-1 truncate text-gray-700 dark:text-gray-300">{w.name}</span>
              <span className="capitalize text-gray-400 dark:text-gray-500">{w.status}</span>
            </li>
          ))}
        </ul>
      )}

      {all.length === 0 && (
        <p className="text-xs text-gray-500 dark:text-gray-400">No worker details available.</p>
      )}
    </div>
  );
}
