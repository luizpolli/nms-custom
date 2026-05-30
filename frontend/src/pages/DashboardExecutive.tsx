/**
 * Executive/Summary Dashboard — aggregated daily KPIs, 7-day sparklines,
 * top offenders, and service health overview.
 */

import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Server,
  TrendingDown,
  TrendingUp,
  Wifi,
} from 'lucide-react';
import { api } from '../lib/api';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';

// ─── API types ────────────────────────────────────────────────────────────────

interface DailyStat {
  label: string;
  value: number | string;
  unit?: string | null;
  delta?: number | null;
}

interface TopOffender {
  device_id: string;
  device_name: string;
  alarm_count: number;
  cpu_avg?: number | null;
}

interface ExecutiveSummaryData {
  generated_at: string;
  uptime_pct: number;
  alarms_new_24h: number;
  alarms_resolved_24h: number;
  mttr_minutes: number | null;
  top_offenders: TopOffender[];
  kpi_sparklines: Record<string, number[]>;
  daily_stats: DailyStat[];
}

interface ServiceImpact {
  service_id: string;
  name: string;
  score: number;
  health_state: string;
}

// ─── Query hooks ─────────────────────────────────────────────────────────────

function useExecutiveSummary() {
  return useQuery({
    queryKey: ['dashboard', 'executive-summary'],
    queryFn: async () => {
      const { data } = await api.get<ExecutiveSummaryData>('/dashboard/executive-summary');
      return data;
    },
    refetchInterval: 120_000,
  });
}

function useServiceHealth() {
  return useQuery({
    queryKey: ['assurance', 'services'],
    queryFn: async () => {
      const { data } = await api.get<ServiceImpact[]>('/assurance/services');
      return data;
    },
    refetchInterval: 60_000,
  });
}

// ─── Sparkline SVG ───────────────────────────────────────────────────────────

function Sparkline({
  values,
  color = '#3b82f6',
  width = 100,
  height = 32,
}: {
  values: number[];
  color?: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) {
    return <div className="h-8 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-800" />;
  }
  const max = Math.max(...values) || 1;
  const min = Math.min(...values);
  const range = max - min || 1;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
  const lastVal = values[values.length - 1];
  const firstVal = values[0];
  const trend = lastVal - firstVal;

  return (
    <div className="flex items-end gap-2">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
        <defs>
          <linearGradient id={`spark-fill-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon
          points={`0,${height} ${pts} ${width},${height}`}
          fill={`url(#spark-fill-${color.replace('#', '')})`}
        />
        <polyline
          points={pts}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Last point dot */}
        {(() => {
          const lastX = width;
          const lastY = height - ((lastVal - min) / range) * (height - 4) - 2;
          return <circle cx={lastX} cy={lastY} r="2.5" fill={color} />;
        })()}
      </svg>
      {trend !== 0 && (
        <span className={`text-xs font-medium ${trend > 0 ? 'text-red-500' : 'text-emerald-500'}`}>
          {trend > 0 ? <TrendingUp className="h-3 w-3 inline" /> : <TrendingDown className="h-3 w-3 inline" />}
          {' '}{Math.abs(trend).toFixed(1)}
        </span>
      )}
    </div>
  );
}

// ─── Big KPI card ─────────────────────────────────────────────────────────────

function KpiTile({
  label,
  value,
  unit,
  icon,
  tone = 'default',
  sparkline,
}: {
  label: string;
  value: number | string;
  unit?: string | null;
  icon: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger';
  sparkline?: number[];
}) {
  const toneClass = {
    default: 'text-gray-800 dark:text-gray-100',
    success: 'text-emerald-600 dark:text-emerald-400',
    warning: 'text-amber-600 dark:text-amber-400',
    danger: 'text-red-600 dark:text-red-400',
  }[tone];

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-start justify-between">
        <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{label}</div>
        <div className="text-gray-400 dark:text-gray-500">{icon}</div>
      </div>
      <div className={`text-3xl font-bold tabular-nums ${toneClass}`}>
        {value}
        {unit && <span className="ml-1 text-base font-normal text-gray-500">{unit}</span>}
      </div>
      {sparkline && sparkline.length > 1 && (
        <Sparkline
          values={sparkline}
          color={tone === 'danger' ? '#ef4444' : tone === 'warning' ? '#f59e0b' : tone === 'success' ? '#10b981' : '#3b82f6'}
          width={120}
          height={28}
        />
      )}
    </div>
  );
}

// ─── Service health badge ────────────────────────────────────────────────────

function serviceHealthVariant(score: number): 'success' | 'warning' | 'danger' | 'neutral' {
  if (score >= 90) return 'success';
  if (score >= 70) return 'warning';
  if (score > 0) return 'danger';
  return 'neutral';
}

// ─── Main page ────────────────────────────────────────────────────────────────

export function DashboardExecutive() {
  const navigate = useNavigate();
  const summary = useExecutiveSummary();
  const services = useServiceHealth();

  const d = summary.data;
  const cpuSparkline = d?.kpi_sparklines?.cpu ?? [];
  const alarmSparkline = d?.kpi_sparklines?.alarms ?? [];

  const uptimeTone: 'success' | 'warning' | 'danger' =
    (d?.uptime_pct ?? 100) >= 99 ? 'success' : (d?.uptime_pct ?? 100) >= 95 ? 'warning' : 'danger';

  const resolutionRatio =
    d && d.alarms_new_24h > 0
      ? Math.round((d.alarms_resolved_24h / d.alarms_new_24h) * 100)
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Executive Summary"
        subtitle="Daily KPIs and network health overview"
        actions={
          <button
            type="button"
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </button>
        }
      />

      {/* KPI tiles row */}
      {summary.isLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      ) : d ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiTile
            label="Network Uptime"
            value={`${d.uptime_pct.toFixed(1)}`}
            unit="%"
            icon={<Wifi className="h-5 w-5" />}
            tone={uptimeTone}
          />
          <KpiTile
            label="New Alarms (24h)"
            value={d.alarms_new_24h}
            icon={<AlertTriangle className="h-5 w-5" />}
            tone={d.alarms_new_24h > 50 ? 'danger' : d.alarms_new_24h > 10 ? 'warning' : 'success'}
            sparkline={alarmSparkline}
          />
          <KpiTile
            label="Resolved (24h)"
            value={d.alarms_resolved_24h}
            icon={<CheckCircle2 className="h-5 w-5" />}
            tone={resolutionRatio !== null && resolutionRatio >= 80 ? 'success' : 'warning'}
          />
          <KpiTile
            label="MTTR"
            value={d.mttr_minutes != null ? d.mttr_minutes.toFixed(0) : 'N/A'}
            unit={d.mttr_minutes != null ? 'min' : undefined}
            icon={<Clock className="h-5 w-5" />}
            tone={d.mttr_minutes != null && d.mttr_minutes <= 30 ? 'success' : d.mttr_minutes != null && d.mttr_minutes <= 120 ? 'warning' : 'danger'}
          />
        </div>
      ) : null}

      {/* Sparklines: CPU 7-day + Alarms 7-day */}
      {d && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-500" />
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">CPU Average — 7 Day Trend</h2>
              </div>
            </CardHeader>
            <div className="p-4">
              {cpuSparkline.length > 1 ? (
                <div>
                  <Sparkline values={cpuSparkline} color="#3b82f6" width={320} height={60} />
                  <div className="mt-2 flex justify-between text-xs text-gray-400">
                    {['7d ago', '6d', '5d', '4d', '3d', '2d', 'Today'].map((l) => (
                      <span key={l}>{l}</span>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState message="Collecting 7-day CPU history…" />
              )}
            </div>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Alarms Per Day — 7 Day Trend</h2>
              </div>
            </CardHeader>
            <div className="p-4">
              {alarmSparkline.length > 1 ? (
                <div>
                  <Sparkline values={alarmSparkline} color="#f59e0b" width={320} height={60} />
                  <div className="mt-2 flex justify-between text-xs text-gray-400">
                    {['7d ago', '6d', '5d', '4d', '3d', '2d', 'Today'].map((l) => (
                      <span key={l}>{l}</span>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState message="Collecting 7-day alarm history…" />
              )}
            </div>
          </Card>
        </div>
      )}

      {/* Top offenders + Service health */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="h-4 w-4 text-red-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Top Offenders (24h)</h2>
            </div>
          </CardHeader>
          {summary.isLoading ? (
            <div className="m-4 h-24 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
          ) : d?.top_offenders.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {d.top_offenders.map((o, rank) => (
                <li key={o.device_id} className="flex items-center gap-3 px-4 py-3 text-sm">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-gray-100 text-xs font-bold text-gray-500 dark:bg-gray-800">
                    {rank + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-gray-800 dark:text-gray-100">{o.device_name}</div>
                    {o.cpu_avg != null && (
                      <div className="text-xs text-gray-500">CPU avg: {o.cpu_avg}%</div>
                    )}
                  </div>
                  <Badge variant={o.alarm_count > 20 ? 'danger' : o.alarm_count > 5 ? 'warning' : 'neutral'}>
                    {o.alarm_count} alarm{o.alarm_count !== 1 ? 's' : ''}
                  </Badge>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No alarm activity in last 24h" />
          )}
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Service Health Summary</h2>
            </div>
          </CardHeader>
          {services.isLoading ? (
            <div className="m-4 h-24 animate-pulse rounded bg-gray-100 dark:bg-gray-800" />
          ) : services.data?.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {services.data.slice(0, 10).map((svc) => (
                <li key={svc.service_id} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium text-gray-800 dark:text-gray-100">{svc.name}</div>
                    <div className="text-xs text-gray-500 capitalize">{svc.health_state}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-20">
                      <div className="h-1.5 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                        <div
                          className={`h-full rounded-full ${svc.score >= 90 ? 'bg-emerald-500' : svc.score >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(svc.score, 100)}%` }}
                        />
                      </div>
                    </div>
                    <Badge variant={serviceHealthVariant(svc.score)}>
                      {svc.score}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No service data available" />
          )}
        </Card>
      </div>

      {/* Daily stats summary row */}
      {d?.daily_stats.length ? (
        <Card>
          <CardHeader title="Daily Stats at a Glance" />
          <div className="flex flex-wrap gap-4 p-4">
            {d.daily_stats.map((stat) => (
              <div key={stat.label} className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-700 dark:bg-gray-800/50">
                <div className="text-xs text-gray-500 dark:text-gray-400">{stat.label}</div>
                <div className="mt-0.5 text-lg font-bold text-gray-900 dark:text-gray-100">
                  {stat.value}
                  {stat.unit && <span className="ml-1 text-xs font-normal text-gray-500">{stat.unit}</span>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {/* Last updated */}
      {d?.generated_at && (
        <p className="text-right text-xs text-gray-400">
          Generated at {new Date(d.generated_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

export default DashboardExecutive;
