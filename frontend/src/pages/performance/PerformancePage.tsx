import { useState, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { RefreshCw } from 'lucide-react';
import { PageHeader, Card, Button, Select } from '../../components/ui';
import { api } from '../../lib/api';
import { StatRow } from './components/StatRow';
import { KPIChart, KPIDataPoint } from './components/KPIChart';
import { DevicePicker } from './components/DevicePicker';
import { TimeRangePicker, TimeRange } from './components/TimeRangePicker';

interface PerformanceSummary {
  cpu_avg: number;
  mem_avg: number;
  top_devices: Array<{ device_id: string; name: string; cpu_5min: number }>;
}

interface AggregatePoint {
  ts: string;
  avg: number;
  min: number;
  max: number;
}

const KPI_OPTIONS = [
  { value: 'cpu_5min', label: 'CPU 5 min' },
  { value: 'cpu_1min', label: 'CPU 1 min' },
  { value: 'mem_used_pct', label: 'Memory (%)' },
  { value: 'if_in_octets_rate', label: 'Inbound traffic' },
  { value: 'if_out_octets_rate', label: 'Outbound traffic' },
];

function defaultRange(): TimeRange {
  const until = new Date();
  const since = new Date(until.getTime() - 3600_000);
  return { since: since.toISOString(), until: until.toISOString() };
}

async function fetchSummary(): Promise<PerformanceSummary> {
  const { data } = await api.get<PerformanceSummary>('/performance/summary');
  return data;
}

async function fetchAggregate(
  deviceId: string,
  kpiType: string,
  range: TimeRange,
): Promise<AggregatePoint[]> {
  const { data } = await api.get<AggregatePoint[]>(
    `/performance/devices/${deviceId}/kpis/aggregate`,
    { params: { kpi_type: kpiType, since: range.since, until: range.until, bucket: '5m' } },
  );
  return data;
}

export function PerformancePage() {
  const queryClient = useQueryClient();
  const [deviceId, setDeviceId] = useState('');
  const [kpiType, setKpiType] = useState('cpu_5min');
  const [range, setRange] = useState<TimeRange>(defaultRange);

  const summaryQuery = useQuery({
    queryKey: ['performance-summary'],
    queryFn: fetchSummary,
    refetchInterval: 30_000,
  });

  const aggregateQuery = useQuery({
    queryKey: ['performance-aggregate', deviceId, kpiType, range],
    queryFn: () => fetchAggregate(deviceId, kpiType, range),
    enabled: Boolean(deviceId),
    refetchInterval: 30_000,
  });

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['performance-summary'] });
    if (deviceId) {
      queryClient.invalidateQueries({ queryKey: ['performance-aggregate', deviceId, kpiType, range] });
    }
  }, [queryClient, deviceId, kpiType, range]);

  const summary = summaryQuery.data;
  const statItems = [
    { label: 'Average CPU (%)', value: summary ? summary.cpu_avg.toFixed(1) : '—', unit: '%' },
    { label: 'Average memory (%)', value: summary ? summary.mem_avg.toFixed(1) : '—', unit: '%' },
    { label: 'Polling status', value: summaryQuery.isLoading ? 'Polling…' : 'Active', trend: 'neutral' as const },
  ];

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Performance"
        subtitle="Network KPIs — Cisco NMS"
        actions={
          <Button variant="outline" size="sm" onClick={handleRefresh} leftIcon={<RefreshCw size={14} />}>
            Refresh
          </Button>
        }
      />

      <StatRow items={statItems} />

      {summary && summary.top_devices.length > 0 && (
        <Card>
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Top devices by CPU
          </p>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary.top_devices} margin={{ top: 4, right: 8, bottom: 24, left: 8 }}>
                <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" />
                <YAxis unit="%" tick={{ fontSize: 10 }} domain={[0, 100]} />
                <Tooltip formatter={(v: number) => [`${v}%`, 'CPU 5 min']} />
                <Bar dataKey="cpu_5min" fill="#3b82f6" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      <Card>
        <div className="flex flex-wrap gap-4 items-end mb-4">
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-500 mb-1">Device</label>
            <DevicePicker value={deviceId} onChange={setDeviceId} />
          </div>
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-500 mb-1">KPI type</label>
            <Select
              value={kpiType}
              onChange={(e) => setKpiType(e.target.value)}
              options={KPI_OPTIONS}
            />
          </div>
        </div>
        <div className="mb-4">
          <label className="block text-xs text-gray-500 mb-1">Time range</label>
          <TimeRangePicker value={range} onChange={setRange} />
        </div>

        {!deviceId && (
          <p className="text-sm text-gray-400 text-center py-8">
            Select a device to view KPIs.
          </p>
        )}

        {deviceId && aggregateQuery.isLoading && (
          <p className="text-sm text-gray-400 text-center py-8">Loading data…</p>
        )}

        {deviceId && aggregateQuery.isError && (
          <p className="text-sm text-red-500 text-center py-8">Failed to load data.</p>
        )}

        {deviceId && aggregateQuery.data && (
          <KPIChart
            data={aggregateQuery.data as KPIDataPoint[]}
            kpiType={kpiType}
          />
        )}
      </Card>
    </div>
  );
}
