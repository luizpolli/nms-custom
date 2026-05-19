import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Bell, Download, RadioTower, Server, Workflow } from 'lucide-react';
import { api } from '../../lib/api';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Card, CardHeader } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/Input';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatCard } from '../../components/ui/StatCard';

type LabScenario = {
  scenario_label?: string | null;
  run_id?: string | null;
  notes?: string | null;
  annotated_at?: string | null;
};

type WorkerStatus = {
  kind: string;
  last_status?: string | null;
  last_run_at?: string | null;
  runs_total: number;
  errors_total: number;
  is_stale: boolean;
};

type EpsBucket = {
  start: string;
  end: string;
  count: number;
  eps: number;
};

type CountBucket = {
  label: string;
  lower_ms?: number | null;
  upper_ms?: number | null;
  count: number;
};

type LabHealth = {
  generated_at: string;
  window_minutes: number;
  scenario: LabScenario;
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
  distributions: {
    bucket_seconds: number;
    raw_sample_eps: EpsBucket[];
    kpi_eps: EpsBucket[];
    alarm_eps: EpsBucket[];
    latency_ms: {
      unit: 'ms';
      sample_count: number;
      buckets: CountBucket[];
      note?: string | null;
    };
    truncated_at: number;
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

function useLabHealth(scenario: LabScenario) {
  return useQuery({
    queryKey: ['lab', 'health', scenario],
    queryFn: async () => {
      const { data } = await api.get<LabHealth>('/lab/health', {
        params: {
          window_minutes: 15,
          scenario_label: scenario.scenario_label || undefined,
          run_id: scenario.run_id || undefined,
          notes: scenario.notes || undefined,
        },
      });
      return data;
    },
    refetchInterval: 10_000,
  });
}

export function LabHealthPage() {
  const [scenario, setScenario] = useState<LabScenario>({ scenario_label: '', run_id: '', notes: '' });
  const lab = useLabHealth(scenario);
  const data = lab.data;
  const staleWorkers = data?.workers.filter((worker) => worker.is_stale) ?? [];
  const activeAlarms = sumSourceState(data?.alarms.by_source_state, 'active');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Lab Health"
        subtitle="Mock traffic, EPS, receiver, worker, and event-bus visibility"
      />

      <Card padding={false}>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Run snapshot</h2>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                {data
                  ? `Generated ${fmtDate(data.generated_at)} · window ${data.window_minutes}m${scenarioSummary(data.scenario)}`
                  : 'Waiting for lab health data'}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              leftIcon={<Download className="h-4 w-4" />}
              disabled={!data}
              onClick={() => data && downloadLabHealthSnapshot(withScenarioDraft(data, scenario))}
            >
              Export JSON
            </Button>
          </div>
        </CardHeader>
        <div className="grid gap-3 border-t border-gray-100 p-4 dark:border-gray-800 sm:grid-cols-3">
          <Input
            label="Scenario label"
            placeholder="mixed soak, trap storm..."
            maxLength={120}
            value={scenario.scenario_label ?? ''}
            onChange={(event) => setScenario((current) => ({ ...current, scenario_label: event.target.value }))}
          />
          <Input
            label="Run ID"
            placeholder="run-001"
            maxLength={80}
            value={scenario.run_id ?? ''}
            onChange={(event) => setScenario((current) => ({ ...current, run_id: event.target.value }))}
          />
          <Input
            label="Notes"
            placeholder="traffic mix, rate, lab host..."
            maxLength={500}
            value={scenario.notes ?? ''}
            onChange={(event) => setScenario((current) => ({ ...current, notes: event.target.value }))}
            hint="Included in /api/lab/health and exported JSON snapshots."
          />
        </div>
      </Card>

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

        <Card padding={false}>
          <CardHeader title="EPS distribution" />
          {data ? (
            <div className="space-y-4 p-4">
              <MiniHistogram title="Raw telemetry samples" buckets={data.distributions.raw_sample_eps} />
              <MiniHistogram title="Telemetry KPIs" buckets={data.distributions.kpi_eps} />
              <MiniHistogram title="Alarms" buckets={data.distributions.alarm_eps} />
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Bucket size: {formatBucketSeconds(data.distributions.bucket_seconds)}. Reads are capped at {data.distributions.truncated_at.toLocaleString()} samples per series.
              </div>
            </div>
          ) : (
            <EmptyState message="No EPS distribution data" />
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
          <CardHeader title="Latency distribution" />
          {data ? (
            <div className="space-y-3 p-4">
              <CountHistogram buckets={data.distributions.latency_ms.buckets} />
              <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>{data.distributions.latency_ms.sample_count.toLocaleString()} latency KPI samples</span>
                <span>Unit: {data.distributions.latency_ms.unit}</span>
              </div>
              {data.distributions.latency_ms.note && (
                <div className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                  {data.distributions.latency_ms.note}
                </div>
              )}
            </div>
          ) : (
            <EmptyState message="No latency histogram data" />
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

function MiniHistogram({ title, buckets }: { title: string; buckets: EpsBucket[] }) {
  const max = Math.max(...buckets.map((bucket) => bucket.eps), 0);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
        <span>{title}</span>
        <span>max {max.toFixed(2)} EPS</span>
      </div>
      <div className="flex h-16 items-end gap-1 rounded-md border border-gray-100 bg-gray-50 p-2 dark:border-gray-800 dark:bg-gray-950/40">
        {buckets.map((bucket) => {
          const height = max > 0 ? Math.max((bucket.eps / max) * 100, 4) : 0;
          return (
            <div
              key={`${bucket.start}-${bucket.end}`}
              className="flex-1 rounded-t bg-blue-500/80 dark:bg-blue-400/80"
              style={{ height: `${height}%` }}
              title={`${fmtTime(bucket.start)}-${fmtTime(bucket.end)}: ${bucket.count} (${bucket.eps.toFixed(2)} EPS)`}
            />
          );
        })}
      </div>
    </div>
  );
}

function CountHistogram({ buckets }: { buckets: CountBucket[] }) {
  const max = Math.max(...buckets.map((bucket) => bucket.count), 0);
  return (
    <div className="space-y-2">
      {buckets.map((bucket) => {
        const width = max > 0 ? Math.max((bucket.count / max) * 100, 3) : 0;
        return (
          <div key={bucket.label} className="grid grid-cols-[5rem_1fr_3rem] items-center gap-2 text-sm">
            <span className="text-gray-600 dark:text-gray-300">{bucket.label}</span>
            <div className="h-3 rounded-full bg-gray-100 dark:bg-gray-800">
              <div className="h-3 rounded-full bg-emerald-500 dark:bg-emerald-400" style={{ width: `${width}%` }} />
            </div>
            <span className="text-right font-medium text-gray-900 dark:text-gray-100">{bucket.count}</span>
          </div>
        );
      })}
    </div>
  );
}

function formatBucketSeconds(seconds: number) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${Math.round(seconds / 3600)}h`;
}

function sumSourceState(states: Record<string, Record<string, number>> | undefined, state: string): number {
  if (!states) return 0;
  return Object.values(states).reduce((sum, row) => sum + (row[state] ?? 0), 0);
}

function fmtDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function fmtTime(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function scenarioSummary(scenario?: LabScenario) {
  if (!scenario) return '';
  const parts = [scenario.scenario_label, scenario.run_id].filter(Boolean);
  return parts.length ? ` · ${parts.join(' · ')}` : '';
}

function cleanScenarioValue(value?: string | null) {
  const normalized = value?.trim().replace(/\s+/g, ' ');
  return normalized || null;
}

function withScenarioDraft(data: LabHealth, scenario: LabScenario): LabHealth {
  const draft = {
    scenario_label: cleanScenarioValue(scenario.scenario_label),
    run_id: cleanScenarioValue(scenario.run_id),
    notes: cleanScenarioValue(scenario.notes),
  };
  const annotated = Boolean(draft.scenario_label || draft.run_id || draft.notes);
  return {
    ...data,
    scenario: {
      ...draft,
      annotated_at: annotated ? (data.scenario.annotated_at ?? data.generated_at) : null,
    },
  };
}

function downloadLabHealthSnapshot(data: LabHealth) {
  const generatedAt = new Date(data.generated_at);
  const stamp = Number.isNaN(generatedAt.getTime())
    ? 'unknown-time'
    : generatedAt.toISOString().replace(/[:.]/g, '-');
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `lab-health-${stamp}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default LabHealthPage;
