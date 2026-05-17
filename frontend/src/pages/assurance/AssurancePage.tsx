import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, GitBranch, HeartPulse, ShieldCheck, Target } from 'lucide-react';
import { Badge, Card, EmptyState, PageHeader, StatCard } from '../../components/ui';
import { api } from '../../lib/api';

type ImpactedDevice = {
  device_id?: string | null;
  name: string;
  source_host?: string | null;
  score: number;
  active_alarms: number;
  worst_severity: string;
  last_seen?: string | null;
};

type CorrelationGroup = {
  group_key: string;
  root_alarm_id?: string | null;
  root_cause: string;
  severity: string;
  category: string;
  state: string;
  active_count: number;
  occurrence_count: number;
  impacted_devices: string[];
  first_seen: string;
  last_seen: string;
};

type TimelineEvent = {
  id: string;
  timestamp: string;
  event_type: string;
  severity: string;
  source_type: string;
  source_host: string;
  message: string;
  correlation_key?: string | null;
};

type AssuranceSummary = {
  network_score: number;
  health_state: string;
  active_alarm_count: number;
  active_group_count: number;
  impacted_device_count: number;
  baseline_breach_count: number;
  top_impacted_devices: ImpactedDevice[];
  top_groups: CorrelationGroup[];
};

export function AssurancePage() {
  const summaryQuery = useQuery({
    queryKey: ['assurance-summary'],
    queryFn: () => api.get<AssuranceSummary>('/assurance/summary').then((r) => r.data),
    refetchInterval: 30_000,
  });
  const timelineQuery = useQuery({
    queryKey: ['assurance-timeline'],
    queryFn: () => api.get<TimelineEvent[]>('/assurance/timeline', { params: { limit: 25 } }).then((r) => r.data),
    refetchInterval: 30_000,
  });

  const summary = summaryQuery.data;
  const scoreTone = !summary ? 'default' : summary.network_score >= 90 ? 'success' : summary.network_score >= 75 ? 'warning' : 'danger';

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Assurance" subtitle="Root-cause groups, health scoring, impacted entities, and event timeline" />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <StatCard title="Network score" value={summary?.network_score ?? '—'} icon={<ShieldCheck className="h-5 w-5" />} tone={scoreTone} loading={summaryQuery.isLoading} />
        <StatCard title="Health state" value={summary?.health_state ?? '—'} icon={<HeartPulse className="h-5 w-5" />} loading={summaryQuery.isLoading} />
        <StatCard title="Active groups" value={summary?.active_group_count ?? 0} icon={<GitBranch className="h-5 w-5" />} tone={(summary?.active_group_count ?? 0) > 0 ? 'warning' : 'success'} loading={summaryQuery.isLoading} />
        <StatCard title="Impacted devices" value={summary?.impacted_device_count ?? 0} icon={<Target className="h-5 w-5" />} tone={(summary?.impacted_device_count ?? 0) > 0 ? 'warning' : 'success'} loading={summaryQuery.isLoading} />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Root-cause correlation groups</h2>
          {!summary?.top_groups?.length ? <EmptyState title="No active groups" description="Related alarms will collapse here by correlation key or group id." /> : (
            <div className="space-y-3">
              {summary.top_groups.map((group) => (
                <div key={group.group_key} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge variant={group.severity as never}>{group.severity}</Badge>
                        <span className="text-sm font-medium text-gray-900 dark:text-white">{group.category}</span>
                      </div>
                      <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">{group.root_cause}</p>
                      <p className="mt-1 text-xs text-gray-500">{group.impacted_devices.join(', ') || 'No impacted device mapped'}</p>
                    </div>
                    <Badge variant={group.state === 'active' ? 'warning' : 'default'}>{group.active_count} active</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Top impacted devices</h2>
          {!summary?.top_impacted_devices?.length ? <EmptyState title="No impacted devices" description="Health scores will drop as active alarms or KPI quality breaches appear." /> : (
            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800"><tr><Th>Device/source</Th><Th>Score</Th><Th>Worst</Th><Th>Active alarms</Th></tr></thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {summary.top_impacted_devices.map((d) => <tr key={`${d.device_id ?? d.source_host}-${d.name}`}><Td>{d.name}</Td><Td><Badge variant={d.score >= 90 ? 'success' : d.score >= 75 ? 'warning' : 'danger'}>{d.score}</Badge></Td><Td><Badge variant={d.worst_severity as never}>{d.worst_severity}</Badge></Td><Td>{d.active_alarms}</Td></tr>)}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2"><AlertTriangle className="h-5 w-5 text-cisco-blue" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white">Event timeline</h2></div>
        {!timelineQuery.data?.length ? <EmptyState title="No recent events" /> : (
          <div className="space-y-2">
            {timelineQuery.data.map((event) => (
              <div key={event.id} className="flex gap-3 rounded-lg border border-gray-200 p-3 text-sm dark:border-gray-700">
                <Badge variant={event.severity as never}>{event.severity}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-gray-900 dark:text-white">{event.event_type} · {event.source_host}</div>
                  <div className="truncate text-gray-600 dark:text-gray-300">{event.message}</div>
                  <div className="text-xs text-gray-500">{new Date(event.timestamp).toLocaleString()} · {event.correlation_key ?? event.source_type}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) { return <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{children}</th>; }
function Td({ children }: { children: React.ReactNode }) { return <td className="px-3 py-2 align-top text-gray-700 dark:text-gray-200">{children}</td>; }

export default AssurancePage;
