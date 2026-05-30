/**
 * DeviceDashboard — rich per-device view with KPI trends, interfaces,
 * active alarms, chassis embed, and service impact.
 *
 * Route: /devices/:id/dashboard
 */

import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  RefreshCw,
  Terminal,
  Cpu,
  MemoryStick,
  Network,
  Bell,
  Activity,
  Server,
  ChevronDown,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { api } from '../../lib/api';
import {
  Button,
  Card,
  CardHeader,
  Spinner,
  EmptyState,
  PageHeader,
  Badge,
} from '../../components/ui';
import { DeviceStatusBadge } from './components/DeviceStatusBadge';

// ─── API types ──────────────────────────────────────────────────────────────

interface KPIPoint {
  timestamp: string;
  value: number;
}

interface AlarmSummary {
  total_active: number;
  critical: number;
  major: number;
  minor: number;
  warning: number;
  recent: RecentAlarm[];
}

interface RecentAlarm {
  id: string;
  severity: string;
  category: string;
  event_type: string;
  message: string;
  state: string;
  last_seen: string | null;
  occurrence_count: number;
}

interface InterfaceSummary {
  if_index: number;
  descr: string | null;
  alias: string | null;
  admin_status: number | null;
  oper_status: number | null;
  speed: number | null;
  in_octets: number | null;
  out_octets: number | null;
  in_errors: number | null;
  out_errors: number | null;
}

interface ServiceInfo {
  service_id: string;
  service_name: string;
  kind: string;
  role: string;
}

interface DeviceDashboardData {
  device_id: string;
  name: string;
  ip_address: string;
  vendor: string | null;
  model: string | null;
  os_type: string | null;
  device_type: string | null;
  status: string;
  location: string | null;
  tags: string[];
  uptime: string | null;
  software_version: string | null;
  cpu_trend: KPIPoint[];
  mem_trend: KPIPoint[];
  interface_trends: Record<string, KPIPoint[]>;
  cpu_now: number | null;
  mem_now: number | null;
  alarms: AlarmSummary;
  interfaces: InterfaceSummary[];
  has_chassis: boolean;
  services: ServiceInfo[];
}

// ─── Sparkline chart ────────────────────────────────────────────────────────

interface SparklineProps {
  points: KPIPoint[];
  color?: string;
  maxY?: number;
  height?: number;
  width?: number;
}

function Sparkline({ points, color = '#3b82f6', maxY, height = 48, width = 300 }: SparklineProps) {
  if (points.length < 2) {
    return (
      <div
        className="flex items-center justify-center rounded border border-dashed border-gray-200 text-[11px] text-gray-400 dark:border-gray-700"
        style={{ height }}
      >
        no data yet
      </div>
    );
  }

  const vals = points.map((p) => p.value);
  const minVal = 0;
  const maxVal = maxY ?? Math.max(...vals, 1);

  const xs = points.map((_, i) => (i / (points.length - 1)) * width);
  const ys = vals.map((v) => height - ((v - minVal) / (maxVal - minVal)) * height);

  const pathD = xs.map((x, i) => `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${ys[i].toFixed(1)}`).join(' ');

  // Area fill
  const areaD =
    pathD +
    ` L ${(width).toFixed(1)} ${height} L 0 ${height} Z`;

  const last = vals[vals.length - 1];
  const strokeColor =
    maxY === 100
      ? last >= 90
        ? '#dc2626'
        : last >= 70
          ? '#ca8a04'
          : color
      : color;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      style={{ height }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={`grad-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.25" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color.replace('#', '')})`} />
      <path d={pathD} fill="none" stroke={strokeColor} strokeWidth={1.5} />
    </svg>
  );
}

// ─── KPI Chart Card ─────────────────────────────────────────────────────────

interface KPICardProps {
  title: string;
  icon: React.ReactNode;
  currentValue: number | null;
  unit: string;
  points: KPIPoint[];
  color?: string;
}

function KPICard({ title, icon, currentValue, unit, points, color }: KPICardProps) {
  const vals = points.map((p) => p.value);
  const avg = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  const max = vals.length ? Math.max(...vals) : null;

  return (
    <Card padding={false}>
      <CardHeader>
        <div className="flex items-center gap-2">
          <span className="text-gray-400 dark:text-gray-500">{icon}</span>
          <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">{title}</span>
          {currentValue !== null && (
            <span className="ml-auto text-2xl font-bold text-gray-900 dark:text-gray-100">
              {currentValue.toFixed(1)}
              <span className="text-sm font-normal text-gray-400 ml-0.5">{unit}</span>
            </span>
          )}
        </div>
      </CardHeader>
      <div className="px-4 pt-2 pb-3">
        <Sparkline points={points} color={color} maxY={100} />
        {avg !== null && max !== null && (
          <div className="flex gap-4 mt-1 text-[11px] text-gray-500 dark:text-gray-400">
            <span>avg {avg.toFixed(1)}{unit}</span>
            <span>max {max.toFixed(1)}{unit}</span>
            <span>{points.length} pts · 24 h</span>
          </div>
        )}
      </div>
    </Card>
  );
}

// ─── Interface trend mini chart ──────────────────────────────────────────────

function InterfaceTrendRow({ ifId, points }: { ifId: string; points: KPIPoint[] }) {
  const vals = points.map((p) => p.value);
  const last = vals.length ? vals[vals.length - 1] : null;
  const max = vals.length ? Math.max(...vals) : null;

  return (
    <div className="flex items-center gap-3 py-2 border-b last:border-0 border-gray-100 dark:border-gray-800">
      <span className="text-xs font-mono text-gray-600 dark:text-gray-300 w-40 truncate">{ifId}</span>
      <div className="flex-1">
        <Sparkline points={points} color="#6366f1" maxY={100} height={32} width={200} />
      </div>
      {last !== null && (
        <span className="text-xs text-gray-700 dark:text-gray-200 w-14 text-right">
          {last.toFixed(1)}%
        </span>
      )}
      {max !== null && (
        <span className="text-[11px] text-gray-400 w-16 text-right">
          max {max.toFixed(1)}%
        </span>
      )}
    </div>
  );
}

// ─── Status pill ────────────────────────────────────────────────────────────

function StatusPill({ value }: { value?: number | null }) {
  const label = value === 1 ? 'up' : value === 2 ? 'down' : 'n/a';
  const cls =
    value === 1
      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
      : value === 2
        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
        : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400';
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

function formatSpeed(speed?: number | null) {
  if (!speed) return '—';
  if (speed >= 1_000_000_000) return `${(speed / 1_000_000_000).toFixed(1)} G`;
  if (speed >= 1_000_000) return `${Math.round(speed / 1_000_000)} M`;
  if (speed >= 1_000) return `${Math.round(speed / 1_000)} K`;
  return `${speed} bps`;
}

function severityBadgeVariant(sev: string): 'critical' | 'major' | 'minor' | 'warning' | 'info' | 'default' {
  const map: Record<string, 'critical' | 'major' | 'minor' | 'warning' | 'info'> = {
    critical: 'critical',
    major: 'major',
    minor: 'minor',
    warning: 'warning',
    info: 'info',
  };
  return map[sev.toLowerCase()] ?? 'default';
}

// ─── Alarm severity bar ──────────────────────────────────────────────────────

function AlarmSeverityBar({ alarms }: { alarms: AlarmSummary }) {
  const total = alarms.total_active || 1; // avoid /0
  const bars = [
    { label: 'Crit', count: alarms.critical, color: 'bg-severity-critical' },
    { label: 'Maj', count: alarms.major, color: 'bg-severity-major' },
    { label: 'Min', count: alarms.minor, color: 'bg-severity-minor' },
    { label: 'Warn', count: alarms.warning, color: 'bg-severity-warning' },
  ];

  return (
    <div className="space-y-1">
      {bars.map((b) => (
        <div key={b.label} className="flex items-center gap-2 text-xs">
          <span className="w-8 text-gray-500 dark:text-gray-400">{b.label}</span>
          <div className="flex-1 h-2 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden">
            <div
              className={`h-full rounded ${b.color}`}
              style={{ width: `${(b.count / total) * 100}%` }}
            />
          </div>
          <span className="w-6 text-right text-gray-700 dark:text-gray-300 font-medium">{b.count}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Expandable interface row ────────────────────────────────────────────────

function InterfaceRow({ iface }: { iface: InterfaceSummary }) {
  const [expanded, setExpanded] = useState(false);
  const totalErrors = (iface.in_errors ?? 0) + (iface.out_errors ?? 0);

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/60 transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="px-3 py-2">
          {expanded ? (
            <ChevronDown className="w-3 h-3 text-gray-400" />
          ) : (
            <ChevronRight className="w-3 h-3 text-gray-400" />
          )}
        </td>
        <td className="px-3 py-2 font-mono text-xs text-gray-700 dark:text-gray-200">{iface.if_index}</td>
        <td className="px-3 py-2 text-sm text-gray-900 dark:text-white">{iface.descr ?? '—'}</td>
        <td className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400">{iface.alias ?? '—'}</td>
        <td className="px-3 py-2"><StatusPill value={iface.admin_status} /></td>
        <td className="px-3 py-2"><StatusPill value={iface.oper_status} /></td>
        <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-300">{formatSpeed(iface.speed)}</td>
        <td className="px-3 py-2 text-xs">
          {totalErrors > 0 ? (
            <span className="text-red-600 dark:text-red-400 font-medium">{totalErrors}</span>
          ) : (
            <span className="text-gray-400">0</span>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 dark:bg-gray-800/40">
          <td colSpan={8} className="px-6 py-3">
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-8 gap-y-1 text-xs">
              <dt className="text-gray-500">In Octets</dt>
              <dd className="font-mono">{iface.in_octets?.toLocaleString() ?? '—'}</dd>
              <dt className="text-gray-500">Out Octets</dt>
              <dd className="font-mono">{iface.out_octets?.toLocaleString() ?? '—'}</dd>
              <dt className="text-gray-500">In Errors</dt>
              <dd className={iface.in_errors ? 'text-red-600 font-medium' : ''}>{iface.in_errors ?? 0}</dd>
              <dt className="text-gray-500">Out Errors</dt>
              <dd className={iface.out_errors ? 'text-red-600 font-medium' : ''}>{iface.out_errors ?? 0}</dd>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}

// ─── Main dashboard page ─────────────────────────────────────────────────────

export function DeviceDashboard() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pollMsg, setPollMsg] = useState('');

  const { data, isLoading, isError } = useQuery<DeviceDashboardData>({
    queryKey: ['device-dashboard', id],
    queryFn: () => api.get(`/devices/${id}/dashboard`).then((r) => r.data),
    enabled: Boolean(id),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const pollMutation = useMutation({
    mutationFn: () => api.post(`/devices/${id}/poll`),
    onSuccess: () => {
      setPollMsg('Poll started successfully.');
      queryClient.invalidateQueries({ queryKey: ['device-dashboard', id] });
      setTimeout(() => setPollMsg(''), 3000);
    },
    onError: () => alert('Failed to poll device'),
  });

  if (isLoading) return <Spinner />;
  if (isError || !data) {
    return (
      <div className="p-6">
        <EmptyState title="Dashboard unavailable" description="Failed to load device dashboard." />
      </div>
    );
  }

  const hasTrends = data.cpu_trend.length > 0 || data.mem_trend.length > 0;
  const hasIfTrends = Object.keys(data.interface_trends).length > 0;

  return (
    <div className="p-4 sm:p-6 space-y-6">
      {/* ── Back + header ── */}
      <div className="flex flex-wrap items-start gap-3">
        <Button variant="ghost" size="sm" onClick={() => navigate(`/devices/${id}`)}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <PageHeader
            title={data.name}
            subtitle={data.ip_address}
            actions={
              <div className="flex items-center gap-2 flex-wrap">
                {pollMsg && <span className="text-green-600 text-sm">{pollMsg}</span>}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => pollMutation.mutate()}
                  disabled={pollMutation.isPending}
                  title="Poll now"
                >
                  <RefreshCw className={`w-4 h-4 mr-1 ${pollMutation.isPending ? 'animate-spin' : ''}`} />
                  Poll
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate(`/devices/${id}`)}
                  title="Device detail"
                >
                  <Terminal className="w-4 h-4 mr-1" />
                  Details
                </Button>
                {data.has_chassis && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate(`/devices/${id}?tab=chassis`)}
                    title="View chassis"
                  >
                    <Server className="w-4 h-4 mr-1" />
                    Chassis
                  </Button>
                )}
              </div>
            }
          />
        </div>
      </div>

      {/* ── Device metadata strip ── */}
      <div className="flex flex-wrap gap-2 items-center">
        <DeviceStatusBadge status={data.status} />
        {data.vendor && <span className="text-sm text-gray-600 dark:text-gray-300">{data.vendor}</span>}
        {data.model && (
          <span className="text-sm text-gray-500 dark:text-gray-400 font-mono">{data.model}</span>
        )}
        {data.os_type && <span className="text-sm text-gray-400">{data.os_type}</span>}
        {data.location && (
          <span className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-gray-500">
            📍 {data.location}
          </span>
        )}
        {data.uptime && (
          <span className="text-xs bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded">
            ↑ {data.uptime}
          </span>
        )}
        {data.software_version && (
          <span className="text-xs bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-300 px-2 py-0.5 rounded font-mono">
            {data.software_version}
          </span>
        )}
        {data.tags.map((tag) => (
          <Badge key={tag} variant="neutral">{tag}</Badge>
        ))}
      </div>

      {/* ── KPI summary row ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 text-center">
          <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">CPU Now</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {data.cpu_now !== null ? `${data.cpu_now.toFixed(1)}%` : '—'}
          </p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Mem Now</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {data.mem_now !== null ? `${data.mem_now.toFixed(1)}%` : '—'}
          </p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Active Alarms</p>
          <p className={`mt-1 text-2xl font-bold ${
            data.alarms.total_active > 0 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-gray-100'
          }`}>
            {data.alarms.total_active}
          </p>
        </Card>
        <Card className="p-3 text-center">
          <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Interfaces</p>
          <p className="mt-1 text-2xl font-bold text-gray-900 dark:text-gray-100">
            {data.interfaces.length}
          </p>
        </Card>
      </div>

      {/* ── KPI trend charts ── */}
      {hasTrends ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <KPICard
            title="CPU Utilization (24 h)"
            icon={<Cpu className="w-4 h-4" />}
            currentValue={data.cpu_now}
            unit="%"
            points={data.cpu_trend}
            color="#3b82f6"
          />
          <KPICard
            title="Memory Utilization (24 h)"
            icon={<MemoryStick className="w-4 h-4" />}
            currentValue={data.mem_now}
            unit="%"
            points={data.mem_trend}
            color="#8b5cf6"
          />
        </div>
      ) : (
        <Card className="p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Activity className="w-4 h-4" />
            <span>No KPI trend data available yet — data accumulates after polling.</span>
          </div>
        </Card>
      )}

      {/* ── Top-5 interface utilization trends ── */}
      {hasIfTrends && (
        <Card padding={false}>
          <CardHeader title="Top Interface Utilization Trends (24 h)" />
          <div className="px-4 py-2 divide-y divide-gray-100 dark:divide-gray-800">
            {Object.entries(data.interface_trends).map(([ifId, points]) => (
              <InterfaceTrendRow key={ifId} ifId={ifId} points={points} />
            ))}
          </div>
        </Card>
      )}

      {/* ── Interfaces + Alarms side-by-side (or stacked on mobile) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Interface table — takes 2/3 */}
        <div className="lg:col-span-2">
          <Card padding={false}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                  Interfaces
                </span>
                <span className="ml-auto text-xs text-gray-400">{data.interfaces.length} total</span>
              </div>
            </CardHeader>
            {data.interfaces.length === 0 ? (
              <div className="p-4">
                <EmptyState title="No interfaces" description="No managed interface data stored for this device." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="w-6 px-3 py-2" />
                      {['Idx', 'Name', 'Alias', 'Admin', 'Oper', 'Speed', 'Errs'].map((h) => (
                        <th
                          key={h}
                          className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {data.interfaces.slice(0, 50).map((iface) => (
                      <InterfaceRow key={iface.if_index} iface={iface} />
                    ))}
                  </tbody>
                </table>
                {data.interfaces.length > 50 && (
                  <p className="px-4 py-2 text-xs text-gray-400 border-t border-gray-100 dark:border-gray-800">
                    Showing first 50 of {data.interfaces.length} interfaces. View all in the Interfaces tab.
                  </p>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Alarms panel — takes 1/3 */}
        <div className="space-y-4">
          <Card padding={false}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bell className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">
                  Active Alarms
                </span>
                {data.alarms.total_active > 0 && (
                  <Badge variant="critical" className="ml-auto">
                    {data.alarms.total_active}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <div className="p-4 space-y-4">
              {/* Severity distribution */}
              <AlarmSeverityBar alarms={data.alarms} />

              {/* Recent alarm list */}
              {data.alarms.recent.length === 0 ? (
                <p className="text-xs text-gray-400 text-center py-2">No active alarms 🎉</p>
              ) : (
                <ul className="space-y-2 mt-2">
                  {data.alarms.recent.map((alarm) => (
                    <li
                      key={alarm.id}
                      className="rounded border border-gray-100 dark:border-gray-800 p-2 space-y-0.5"
                    >
                      <div className="flex items-center gap-1.5">
                        <Badge variant={severityBadgeVariant(alarm.severity)}>
                          {alarm.severity}
                        </Badge>
                        <span className="text-xs text-gray-500 dark:text-gray-400 truncate flex-1">
                          {alarm.event_type}
                        </span>
                      </div>
                      <p className="text-xs text-gray-700 dark:text-gray-200 line-clamp-2">
                        {alarm.message}
                      </p>
                      {alarm.last_seen && (
                        <p className="text-[10px] text-gray-400">
                          {new Date(alarm.last_seen).toLocaleString()}
                          {alarm.occurrence_count > 1 && ` · ×${alarm.occurrence_count}`}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <Link
                to={`/alarms?device_id=${data.device_id}`}
                className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                View all alarms for this device
              </Link>
            </div>
          </Card>
        </div>
      </div>

      {/* ── Chassis embed (if supported) ── */}
      {data.has_chassis && (
        <Card padding={false}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Server className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Chassis View</span>
              <Link
                to={`/devices/${id}?tab=chassis`}
                className="ml-auto flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                Full chassis view
              </Link>
            </div>
          </CardHeader>
          <div className="p-4 text-sm text-gray-500 dark:text-gray-400">
            This device has a chassis profile.{' '}
            <Link
              to={`/devices/${id}?tab=chassis`}
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              Open the Chassis tab
            </Link>{' '}
            on the device detail page for the interactive component view.
          </div>
        </Card>
      )}

      {/* ── Service impact ── */}
      {data.services.length > 0 && (
        <Card padding={false}>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-200">Service Impact</span>
              <span className="ml-auto text-xs text-gray-400">
                {data.services.length} service{data.services.length !== 1 ? 's' : ''}
              </span>
            </div>
          </CardHeader>
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {data.services.map((svc) => (
              <div key={svc.service_id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {svc.service_name}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {svc.kind} · role: {svc.role}
                  </p>
                </div>
                <Link
                  to="/services"
                  className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline shrink-0"
                >
                  <ExternalLink className="w-3 h-3" />
                  View
                </Link>
              </div>
            ))}
          </div>
        </Card>
      )}

      {data.services.length === 0 && (
        <Card className="p-4">
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center">
            This device is not a member of any services.
          </p>
        </Card>
      )}
    </div>
  );
}
