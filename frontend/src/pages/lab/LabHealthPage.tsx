import { useQuery } from '@tanstack/react-query';
import { Activity, Bell, RadioTower, Server, Workflow } from 'lucide-react';
import { api } from '../../lib/api';
import { Badge } from '../../components/ui/Badge';
import { Card, CardHeader } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatCard } from '../../components/ui/StatCard';

type WorkerStatus = {
  kind: string;
  last_status?: string | null;
  last_run_at?: string | null;
  runs_total: number;
  errors_total: number;
  is_stale: boolean;
};

type LabHealth = {
  generated_at: string;
  window_minutes: number;
  mock_devices: Array<{
    id: string;
    name: string;
    ip_address: string;
    status: string;
    platform_family?: string | null;
    updated_at?: string | null;
  }>;
  telemetry: {
    raw_samples_total: number;
    raw_samples_recent: number;
    raw_samples_eps: number;
    kpis_total: number;
    kpis_recent: number;
    kpis_eps: number;
    last_raw_sample_at?: string | null;
    last_kpi_at?: string | null;
  };
  alarms: {
    by_source_state: Record<string, Record<string, number>>;
    recent_by_source: Record<string, number>;
    recent_eps: number;
  };
  event_bus: {
    available: boolean;
    stream?: string;
    stream_length: number;
    recent_count: number;
    recent_eps?: number;
    pending_total?: number;
    recent_by_type?: Record<string, number>;
    recent_by_source?: Record<string, number>;
    groups: Array<{ name: string; consumers: number; pending: number; last_delivered_id?: string }>;
    error?: string;
  };
  workers: WorkerStatus[];
  summary: {
    mock_device_count: number;
    stale_worker_count: number;
    event_bus_pending: number;
  };
};

function useLabHealth() {
  return useQuery({
    queryKey: ['lab', 'health'],
    queryFn: async () => {
      const { data } = await api.get<LabHealth>('/lab/health', { params: { window_minutes: 15 } });
      return data;
    },
    refetchInterval: 10_000,
  });
}

export function LabHealthPage() {
  const lab = useLabHealth();
  const data = lab.data;
  const staleWorkers = data?.workers.filter((worker) => worker.is_stale) ?? [];
  const activeAlarms = sumSourceState(data?.alarms.by_source_state, 'active');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Lab Health"
        subtitle="Mock traffic, EPS, receiver, worker, and event-bus visibility"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard
          icon={<Server className="h-5 w-5" />}
          label="Mock devices"
          value={data?.summary.mock_device_count ?? '—'}
          loading={lab.isLoading}
        />
        <StatCard
          icon={<RadioTower className="h-5 w-5" />}
          label="Telemetry EPS"
          value={data ? data.telemetry.raw_samples_eps.toFixed(2) : '—'}
          loading={lab.isLoading}
        />
        <StatCard
          icon={<Bell className="h-5 w-5" />}
          label="Alarm EPS"
          value={data ? data.alarms.recent_eps.toFixed(2) : '—'}
          loading={lab.isLoading}
          tone={activeAlarms > 0 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<Workflow className="h-5 w-5" />}
          label="Event bus EPS"
          value={data?.event_bus.recent_eps?.toFixed(2) ?? '—'}
          loading={lab.isLoading}
          tone={(data?.summary.event_bus_pending ?? 0) > 0 ? 'warning' : 'default'}
          trend={(data?.summary.event_bus_pending ?? 0) > 0 ? `${data?.summary.event_bus_pending} pending` : 'no pending'}
          trendUp={(data?.summary.event_bus_pending ?? 0) === 0}
        />
        <StatCard
          icon={<Activity className="h-5 w-5" />}
          label="Stale workers"
          value={data?.summary.stale_worker_count ?? '—'}
          loading={lab.isLoading}
          tone={staleWorkers.length ? 'danger' : 'success'}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card padding={false}>
          <CardHeader title="Mock devices" />
          {data?.mock_devices.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800">
                  <tr>
                    <th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">IP</th>
                    <th className="px-4 py-2">Status</th>
                    <th className="px-4 py-2">Platform</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                  {data.mock_devices.map((device) => (
                    <tr key={device.id}>
                      <td className="px-4 py-2 font-medium">{device.name}</td>
                      <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{device.ip_address}</td>
                      <td className="px-4 py-2"><Badge variant="info">{device.status}</Badge></td>
                      <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{device.platform_family ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState message="No mock devices found. Run make sim-device or make sim-run." />
          )}
        </Card>

        <Card padding={false}>
          <CardHeader title={`Telemetry window (${data?.window_minutes ?? 15}m)`} />
          {data ? (
            <div className="grid grid-cols-2 gap-4 p-4 text-sm">
              <Metric label="Raw samples total" value={data.telemetry.raw_samples_total} />
              <Metric label="Raw samples recent" value={data.telemetry.raw_samples_recent} />
              <Metric label="Telemetry KPIs total" value={data.telemetry.kpis_total} />
              <Metric label="Telemetry KPIs recent" value={data.telemetry.kpis_recent} />
              <Metric label="Last raw sample" value={fmtDate(data.telemetry.last_raw_sample_at)} />
              <Metric label="Last KPI" value={fmtDate(data.telemetry.last_kpi_at)} />
            </div>
          ) : (
            <EmptyState message="No telemetry data" />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card padding={false}>
          <CardHeader title="Alarm sources" />
          {data ? (
            <div className="space-y-3 p-4">
              {Object.entries(data.alarms.by_source_state).map(([source, states]) => (
                <div key={source} className="rounded-md border border-gray-200 p-3 dark:border-gray-800">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="font-medium">{source}</span>
                    <Badge variant="info">recent {data.alarms.recent_by_source[source] ?? 0}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    {Object.entries(states).map(([state, count]) => (
                      <Badge key={state} variant={state === 'active' ? 'warning' : state === 'cleared' ? 'success' : 'info'}>
                        {state}: {count}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No alarm data" />
          )}
        </Card>

        <Card padding={false}>
          <CardHeader title="Event bus" />
          {data?.event_bus.available ? (
            <div className="space-y-4 p-4 text-sm">
              <div className="grid grid-cols-2 gap-4">
                <Metric label="Stream" value={data.event_bus.stream ?? '—'} />
                <Metric label="Stream length" value={data.event_bus.stream_length} />
                <Metric label="Recent events" value={data.event_bus.recent_count} />
                <Metric label="Pending total" value={data.event_bus.pending_total ?? 0} />
              </div>
              <TopMap title="Recent by source" values={data.event_bus.recent_by_source ?? {}} />
              <TopMap title="Recent by type" values={data.event_bus.recent_by_type ?? {}} />
            </div>
          ) : (
            <EmptyState message={data?.event_bus.error ?? 'Event bus unavailable'} />
          )}
        </Card>
      </div>

      <Card padding={false}>
        <CardHeader title="Workers" />
        {data?.workers.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-gray-200 text-xs uppercase text-gray-500 dark:border-gray-800">
                <tr>
                  <th className="px-4 py-2">Worker</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Runs</th>
                  <th className="px-4 py-2">Errors</th>
                  <th className="px-4 py-2">Last run</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {data.workers.map((worker) => (
                  <tr key={worker.kind}>
                    <td className="px-4 py-2 font-medium">{worker.kind}</td>
                    <td className="px-4 py-2">
                      <Badge variant={worker.is_stale ? 'critical' : worker.last_status === 'error' ? 'major' : 'success'}>
                        {worker.is_stale ? 'stale' : worker.last_status ?? 'unknown'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">{worker.runs_total}</td>
                    <td className="px-4 py-2">{worker.errors_total}</td>
                    <td className="px-4 py-2 text-gray-600 dark:text-gray-300">{fmtDate(worker.last_run_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="No worker heartbeats" />
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
      <div className="mt-1 font-semibold text-gray-900 dark:text-gray-100">{value}</div>
    </div>
  );
}

function TopMap({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return (
    <div>
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{title}</div>
      {entries.length ? (
        <div className="flex flex-wrap gap-2">
          {entries.map(([key, value]) => <Badge key={key} variant="info">{key}: {value}</Badge>)}
        </div>
      ) : (
        <div className="text-sm text-gray-500">No recent events</div>
      )}
    </div>
  );
}

function sumSourceState(states: Record<string, Record<string, number>> | undefined, state: string): number {
  if (!states) return 0;
  return Object.values(states).reduce((sum, row) => sum + (row[state] ?? 0), 0);
}

function fmtDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

export default LabHealthPage;
