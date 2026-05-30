import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Cpu, Server, ShieldCheck, Activity, TrendingUp, Wifi, LayoutGrid, BarChart2, MonitorPlay } from 'lucide-react';
import { api } from '../lib/api';
import { useAlarmWebSocket } from '../lib/ws';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import type { Alarm, AlarmSummary, Device, DeviceStatus, PerformanceSummary } from '../lib/types';

// ─── API types ────────────────────────────────────────────────────────────────

interface TrendPoint {
  ts: string;
  cpu_avg: number | null;
  mem_avg: number | null;
  intf_avg: number | null;
}

interface DeviceTrendSeries {
  device_id: string;
  device_name: string;
  points: TrendPoint[];
}

interface TrendsResponse {
  hours: number;
  buckets: number;
  series: DeviceTrendSeries[];
}

interface InterfaceUtilItem {
  device_id: string;
  device_name: string;
  interface: string;
  utilization: number;
  direction: string;
}

interface InterfaceUtilResponse {
  items: InterfaceUtilItem[];
}

interface AlarmBucket {
  ts: string;
  raised: number;
  cleared: number;
}

interface AlarmTrendResponse {
  hours: number;
  buckets: number;
  data: AlarmBucket[];
}

// ─── Query hooks ──────────────────────────────────────────────────────────────

function useDevices() {
  return useQuery({
    queryKey: ['devices', 'dashboard-status'],
    queryFn: async () => {
      const { data } = await api.get<Device[]>('/devices', { params: { limit: 1000 } });
      return data;
    },
  });
}

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

function useRecentAlarms() {
  return useQuery({
    queryKey: ['alarms', 'recent'],
    queryFn: async () => {
      const { data } = await api.get<Alarm[]>('/alarms', { params: { limit: 5 } });
      return data;
    },
    refetchInterval: 30_000,
  });
}

function useAssuranceSummary() {
  return useQuery({
    queryKey: ['assurance', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<{ network_score: number; health_state: string }>('/assurance/summary');
      return data;
    },
    refetchInterval: 30_000,
  });
}

function useDashboardTrends(hours = 24) {
  return useQuery({
    queryKey: ['dashboard', 'trends', hours],
    queryFn: async () => {
      const { data } = await api.get<TrendsResponse>('/dashboard/trends', { params: { hours, top_n: 5, buckets: 24 } });
      return data;
    },
    refetchInterval: 60_000,
  });
}

function useInterfaceUtil() {
  return useQuery({
    queryKey: ['dashboard', 'interface-utilization'],
    queryFn: async () => {
      const { data } = await api.get<InterfaceUtilResponse>('/dashboard/interface-utilization', { params: { limit: 8 } });
      return data;
    },
    refetchInterval: 60_000,
  });
}

function useAlarmTrend(hours = 24) {
  return useQuery({
    queryKey: ['dashboard', 'alarm-trend', hours],
    queryFn: async () => {
      const { data } = await api.get<AlarmTrendResponse>('/dashboard/alarm-trend', { params: { hours, buckets: 24 } });
      return data;
    },
    refetchInterval: 60_000,
  });
}

// ─── SVG chart helpers ────────────────────────────────────────────────────────

const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
];

function SparkPolyline({
  values,
  width = 120,
  height = 32,
  color = '#3b82f6',
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const nonNull = values.filter((v): v is number => v !== null);
  if (nonNull.length < 2) return <div className="h-8 w-full rounded bg-gray-100 dark:bg-gray-800 animate-pulse" />;
  const max = Math.max(...nonNull) || 1;
  const min = Math.min(...nonNull);
  const range = max - min || 1;
  const pts = values
    .map((v, i) => {
      if (v === null) return null;
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(' ');
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function MultiLineChart({
  series,
  width = 400,
  height = 120,
}: {
  series: { label: string; values: (number | null)[]; color: string }[];
  width?: number;
  height?: number;
}) {
  const allVals = series.flatMap((s) => s.values).filter((v): v is number => v !== null);
  if (!allVals.length) return <EmptyState message="No trend data yet" />;

  const max = Math.max(...allVals) || 1;
  const numBuckets = series[0]?.values.length ?? 24;

  function toSvgPath(values: (number | null)[]): string {
    const segments: string[] = [];
    let inSegment = false;
    values.forEach((v, i) => {
      if (v === null) { inSegment = false; return; }
      const x = (i / (numBuckets - 1)) * width;
      const y = height - (v / max) * (height - 8) - 4;
      if (!inSegment) { segments.push(`M ${x.toFixed(1)} ${y.toFixed(1)}`); inSegment = true; }
      else { segments.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`); }
    });
    return segments.join(' ');
  }

  return (
    <div className="space-y-2">
      <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="rounded">
        {[0, 25, 50, 75, 100].map((pct) => {
          const y = height - (pct / 100) * (height - 8) - 4;
          return <line key={pct} x1={0} y1={y} x2={width} y2={y} stroke="currentColor" strokeOpacity="0.08" strokeWidth="1" />;
        })}
        {series.map((s) => (
          <path key={s.label} d={toSvgPath(s.values)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        ))}
      </svg>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {series.map((s) => (
          <div key={s.label} className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
            <span className="inline-block h-2 w-4 rounded-sm" style={{ backgroundColor: s.color }} />
            <span className="truncate max-w-[8rem]">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlarmTrendChart({ data }: { data: AlarmBucket[] }) {
  if (!data.length) return <EmptyState message="No alarm trend data" />;
  const maxVal = Math.max(...data.map((d) => Math.max(d.raised, d.cleared)), 1);
  const width = 400;
  const height = 100;
  const barW = width / data.length - 1;

  return (
    <svg width="100%" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {data.map((bucket, i) => {
        const x = i * (width / data.length);
        const raisedH = (bucket.raised / maxVal) * (height - 8);
        const clearedH = (bucket.cleared / maxVal) * (height - 8);
        return (
          <g key={bucket.ts}>
            <rect x={x + 1} y={height - raisedH} width={barW * 0.5} height={raisedH} fill="#ef4444" fillOpacity="0.7" rx="1" />
            <rect x={x + barW * 0.5 + 1} y={height - clearedH} width={barW * 0.5} height={clearedH} fill="#10b981" fillOpacity="0.7" rx="1" />
          </g>
        );
      })}
    </svg>
  );
}

function HealthHeatmap({ devices }: { devices: Device[] }) {
  if (!devices.length) return <EmptyState message="No devices" />;
  function healthColor(status: DeviceStatus) {
    if (status === 'reachable') return 'bg-emerald-500';
    if (status === 'unreachable') return 'bg-red-500';
    if (status === 'polling') return 'bg-blue-400';
    return 'bg-gray-400';
  }
  return (
    <div className="flex flex-wrap gap-1.5 p-2">
      {devices.slice(0, 80).map((d) => (
        <div
          key={d.id}
          title={`${d.name} — ${d.status}`}
          className={`h-4 w-4 rounded-sm ${healthColor(d.status)} cursor-pointer opacity-80 hover:opacity-100 hover:scale-110 transition-transform`}
        />
      ))}
      {devices.length > 80 && <span className="text-xs text-gray-400 self-center">+{devices.length - 80} more</span>}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

function Dashboard() {
  const navigate = useNavigate();
  const devices = useDevices();
  const alarms = useAlarmSummary();
  const recentAlarms = useRecentAlarms();
  const perf = usePerformanceSummary();
  const assurance = useAssuranceSummary();
  const ws = useAlarmWebSocket();
  const trends = useDashboardTrends();
  const intfUtil = useInterfaceUtil();
  const alarmTrend = useAlarmTrend();

  const activeAlarms =
    (alarms.data?.critical ?? 0) +
    (alarms.data?.major ?? 0) +
    (alarms.data?.minor ?? 0) +
    (alarms.data?.warning ?? 0);

  const cpuSeries = (trends.data?.series ?? []).map((s, i) => ({
    label: s.device_name,
    values: s.points.map((p) => p.cpu_avg),
    color: CHART_COLORS[i % CHART_COLORS.length],
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Network status overview"
        actions={
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => navigate('/dashboard/executive')}
              className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              <BarChart2 className="h-3.5 w-3.5" />
              Executive View
            </button>
            <button
              type="button"
              onClick={() => navigate('/dashboard/noc')}
              className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              <MonitorPlay className="h-3.5 w-3.5" />
              NOC Board
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={<Server className="h-5 w-5" />} label="Devices" value={devices.data?.length ?? '—'} loading={devices.isLoading} />
        <StatCard icon={<AlertTriangle className="h-5 w-5" />} label="Active alarms" value={activeAlarms} loading={alarms.isLoading} tone={activeAlarms > 0 ? 'warning' : 'default'} />
        <StatCard icon={<Cpu className="h-5 w-5" />} label="Average CPU" value={perf.data?.cpu_avg != null ? `${perf.data.cpu_avg.toFixed(1)}%` : '—'} loading={perf.isLoading} />
        <StatCard
          icon={<ShieldCheck className="h-5 w-5" />}
          label="Assurance score"
          value={assurance.data?.network_score ?? '—'}
          loading={assurance.isLoading}
          tone={(assurance.data?.network_score ?? 100) >= 90 ? 'success' : (assurance.data?.network_score ?? 100) >= 75 ? 'warning' : 'danger'}
          trend={assurance.data?.health_state}
          trendUp={(assurance.data?.network_score ?? 100) >= 90}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">CPU Utilization Trends (24h)</h2>
              <span className="text-xs text-gray-500">— Top 5 devices</span>
            </div>
          </CardHeader>
          <div className="px-4 pb-4 pt-3">
            {trends.isLoading ? (
              <div className="h-32 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
            ) : cpuSeries.length > 0 ? (
              <MultiLineChart series={cpuSeries} height={120} />
            ) : (
              <EmptyState message="No KPI trend data yet" />
            )}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-red-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Alarm Trend (24h)</h2>
              <span className="text-xs text-gray-500">— Raised vs cleared per hour</span>
            </div>
          </CardHeader>
          <div className="px-4 pb-4 pt-3">
            {alarmTrend.isLoading ? (
              <div className="h-24 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
            ) : (
              <>
                <AlarmTrendChart data={alarmTrend.data?.data ?? []} />
                <div className="mt-2 flex gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><span className="inline-block h-2 w-3 rounded bg-red-500/70" /> Raised</span>
                  <span className="flex items-center gap-1"><span className="inline-block h-2 w-3 rounded bg-emerald-500/70" /> Cleared</span>
                </div>
              </>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Alarms by severity" />
          {alarms.data ? (
            <div className="space-y-2 p-4">
              <SeverityRow label="Critical" count={alarms.data.critical ?? alarms.data.by_severity?.critical ?? 0} variant="critical" />
              <SeverityRow label="Major" count={alarms.data.major ?? alarms.data.by_severity?.major ?? 0} variant="major" />
              <SeverityRow label="Minor" count={alarms.data.minor ?? alarms.data.by_severity?.minor ?? 0} variant="minor" />
              <SeverityRow label="Warning" count={alarms.data.warning ?? alarms.data.by_severity?.warning ?? 0} variant="warning" />
              <SeverityRow label="Info" count={alarms.data.info ?? alarms.data.by_severity?.info ?? 0} variant="info" />
            </div>
          ) : (
            <EmptyState message="No alarm data" />
          )}
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-amber-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Top devices by CPU</h2>
            </div>
          </CardHeader>
          {perf.data?.top_devices?.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {perf.data.top_devices.slice(0, 10).map((d) => {
                const sparkValues = (trends.data?.series.find((s) => s.device_id === String(d.device_id))?.points ?? []).map((p) => p.cpu_avg);
                return (
                  <li key={d.device_id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                    <span className="truncate flex-1">{d.name}</span>
                    {sparkValues.length > 1 && <SparkPolyline values={sparkValues} width={80} height={24} color="#f59e0b" />}
                    <Badge variant="info">{d.cpu_5min?.toFixed(1) ?? '—'}%</Badge>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState message="No KPI data" />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <LayoutGrid className="h-4 w-4 text-emerald-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Device Health Heatmap</h2>
              <span className="text-xs text-gray-500">— each tile = one device</span>
            </div>
          </CardHeader>
          {devices.isLoading ? (
            <div className="m-4 h-24 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
          ) : (
            <>
              <HealthHeatmap devices={devices.data ?? []} />
              <div className="flex gap-4 px-4 pb-3 text-xs text-gray-500">
                <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm bg-emerald-500" /> Reachable</span>
                <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm bg-red-500" /> Unreachable</span>
                <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm bg-blue-400" /> Polling</span>
                <span className="flex items-center gap-1"><span className="inline-block h-3 w-3 rounded-sm bg-gray-400" /> Unknown</span>
              </div>
            </>
          )}
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Wifi className="h-4 w-4 text-blue-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Top Interface Utilization</h2>
              <span className="text-xs text-gray-500">— 1h avg</span>
            </div>
          </CardHeader>
          {intfUtil.isLoading ? (
            <div className="m-4 h-24 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
          ) : intfUtil.data?.items.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {intfUtil.data.items.map((item) => (
                <li key={`${item.device_id}-${item.interface}`} className="flex items-center gap-3 px-4 py-2 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-gray-800 dark:text-gray-100">{item.interface}</div>
                    <div className="truncate text-gray-500">{item.device_name}</div>
                  </div>
                  <div className="w-24">
                    <div className="mb-0.5 flex justify-between text-[10px] text-gray-500">
                      <span>{item.direction}</span>
                      <span>{item.utilization.toFixed(1)}%</span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className={`h-full rounded-full ${item.utilization >= 90 ? 'bg-red-500' : item.utilization >= 70 ? 'bg-amber-500' : 'bg-blue-500'}`}
                        style={{ width: `${Math.min(item.utilization, 100)}%` }}
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No interface utilization data" />
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Recent Alarms" />
          {recentAlarms.data?.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {recentAlarms.data.map((alarm) => (
                <li key={alarm.id}>
                  <button
                    type="button"
                    onClick={() => navigate('/alarms')}
                    className="grid w-full grid-cols-[auto,minmax(0,1fr),auto] items-center gap-3 px-4 py-3 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-800/50"
                  >
                    <Badge variant={alarm.severity}>{alarm.severity}</Badge>
                    <div className="min-w-0">
                      <div className="truncate font-medium text-gray-800 dark:text-gray-100">
                        {alarm.source_host ?? alarm.source ?? 'unknown source'}
                      </div>
                      <div className="truncate text-xs text-gray-500 dark:text-gray-400">{alarm.message}</div>
                    </div>
                    <span className="whitespace-nowrap text-xs text-gray-500">
                      {timeAgo(alarm.last_seen ?? alarm.raised_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No alarms recorded yet" />
          )}
        </Card>

        <Card>
          <CardHeader title="Device Status" />
          {devices.data?.length ? (
            <div className="flex flex-wrap gap-2 p-4">
              {deviceStatusRows(devices.data).map(({ status, count }) => (
                <Badge key={status} variant={deviceStatusVariant(status)} className="capitalize">
                  {status}: {count}
                </Badge>
              ))}
            </div>
          ) : (
            <EmptyState message="No devices discovered yet" />
          )}
        </Card>
      </div>

      {ws.lastAlarm && (
        <Card>
          <CardHeader title="Last received alarm" />
          <div className="space-y-1 p-4 text-sm">
            <div>
              <Badge variant={ws.lastAlarm.severity as never}>{ws.lastAlarm.severity}</Badge>{' '}
              <span className="font-medium">{ws.lastAlarm.event_type ?? 'Alarm'}</span>
            </div>
            <div className="text-gray-600 dark:text-gray-400">{ws.lastAlarm.message}</div>
            <div className="text-xs text-gray-500">
              {ws.lastAlarm.source_host ?? ws.lastAlarm.source ?? 'unknown source'} · {new Date(ws.lastAlarm.last_seen ?? ws.lastAlarm.raised_at).toLocaleString()}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function timeAgo(value?: string) {
  if (!value) return '—';
  const ts = new Date(value).getTime();
  if (Number.isNaN(ts)) return '—';
  const seconds = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function deviceStatusRows(devices: Device[]) {
  const counts: Record<DeviceStatus, number> = { reachable: 0, unreachable: 0, unknown: 0, polling: 0 };
  devices.forEach((device) => {
    const status = device.status in counts ? device.status : 'unknown';
    counts[status] += 1;
  });
  return (Object.entries(counts) as Array<[DeviceStatus, number]>).map(([status, count]) => ({ status, count }));
}

function deviceStatusVariant(status: DeviceStatus) {
  if (status === 'reachable') return 'success';
  if (status === 'unreachable') return 'danger';
  if (status === 'polling') return 'info';
  return 'neutral';
}

function SeverityRow({ label, count, variant }: { label: string; count: number; variant: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      <Badge variant={variant as never}>{count}</Badge>
    </div>
  );
}

export default Dashboard;
