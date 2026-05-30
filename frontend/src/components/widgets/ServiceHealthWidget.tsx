import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { EmptyState } from '../ui/EmptyState';

interface ServiceScore {
  service_id: string;
  service_name: string;
  score: number;
  state: string;
}

interface ServiceHealthSummary {
  services: ServiceScore[];
  overall_score?: number;
}

function useServiceHealth() {
  return useQuery({
    queryKey: ['services', 'health-summary'],
    queryFn: async () => {
      const { data } = await api.get<ServiceHealthSummary>('/services/health');
      return data;
    },
    refetchInterval: 30_000,
    retry: 1,
  });
}

function scoreClass(score: number) {
  if (score >= 90) return 'text-green-600 dark:text-green-400';
  if (score >= 70) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

export function ServiceHealthWidget() {
  const { data, isLoading, error } = useServiceHealth();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error) return <div className="p-4 text-sm text-red-500">Service health data unavailable.</div>;

  const services = data?.services ?? [];
  if (!services.length) return <EmptyState message="No services monitored" />;

  return (
    <div className="overflow-auto">
      {data?.overall_score != null && (
        <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2 dark:border-gray-800">
          <span className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Overall</span>
          <span className={`font-bold ${scoreClass(data.overall_score)}`}>{data.overall_score}</span>
        </div>
      )}
      <ul className="divide-y divide-gray-100 dark:divide-gray-800">
        {services.map((svc) => (
          <li key={svc.service_id} className="flex items-center justify-between px-3 py-2 text-sm">
            <span className="truncate text-gray-800 dark:text-gray-100">{svc.service_name}</span>
            <div className="ml-2 flex items-center gap-2 shrink-0">
              <span className="text-xs text-gray-500 capitalize">{svc.state}</span>
              <span className={`font-semibold ${scoreClass(svc.score)}`}>{svc.score}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
