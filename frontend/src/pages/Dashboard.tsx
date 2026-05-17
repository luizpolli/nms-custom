import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Cpu, Server, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import { useAlarmWebSocket } from '../lib/ws';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { StatCard } from '../components/ui/StatCard';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import type { AlarmSummary, Device, PerformanceSummary } from '../lib/types';

function useDevicesCount() {
  return useQuery({
    queryKey: ['devices', 'count'],
    queryFn: async () => {
      const { data } = await api.get<Device[]>('/devices', { params: { limit: 1000 } });
      return data.length;
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

function Dashboard() {
  const devices = useDevicesCount();
  const alarms = useAlarmSummary();
  const perf = usePerformanceSummary();
  const assurance = useAssuranceSummary();
  const ws = useAlarmWebSocket();

  const activeAlarms =
    (alarms.data?.critical ?? 0) +
    (alarms.data?.major ?? 0) +
    (alarms.data?.minor ?? 0) +
    (alarms.data?.warning ?? 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Network status overview"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Server className="h-5 w-5" />}
          label="Devices"
          value={devices.data ?? '—'}
          loading={devices.isLoading}
        />
        <StatCard
          icon={<AlertTriangle className="h-5 w-5" />}
          label="Active alarms"
          value={activeAlarms}
          loading={alarms.isLoading}
          tone={activeAlarms > 0 ? 'warning' : 'default'}
        />
        <StatCard
          icon={<Cpu className="h-5 w-5" />}
          label="Average CPU"
          value={perf.data?.cpu_avg != null ? `${perf.data.cpu_avg.toFixed(1)}%` : '—'}
          loading={perf.isLoading}
        />
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
          <CardHeader title="Top devices by CPU" />
          {perf.data?.top_devices?.length ? (
            <ul className="divide-y divide-gray-200 dark:divide-gray-800">
              {perf.data.top_devices.slice(0, 10).map((d) => (
                <li
                  key={d.device_id}
                  className="flex items-center justify-between px-4 py-2 text-sm"
                >
                  <span className="truncate">{d.name}</span>
                  <Badge variant="info">{d.cpu_5min?.toFixed(1) ?? '—'}%</Badge>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState message="No KPI data" />
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

function SeverityRow({
  label,
  count,
  variant,
}: {
  label: string;
  count: number;
  variant: string;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span>{label}</span>
      <Badge variant={variant as never}>{count}</Badge>
    </div>
  );
}

export default Dashboard;
