import { useState, useCallback } from 'react';
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
import { InstancePicker } from './components/InstancePicker';
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

const SNMP_KPI_OPTIONS = [
  { value: 'cpu_5min', label: 'CPU 5 min' },
  { value: 'cpu_1min', label: 'CPU 1 min' },
  { value: 'mem_used_pct', label: 'Memory (%)' },
  { value: 'if_in_octets_rate', label: 'Inbound traffic' },
  { value: 'if_out_octets_rate', label: 'Outbound traffic' },
];

const BULKSTATS_PREFIX = 'bulkstats_';

interface BulkstatsCatalogEntry {
  metric_name: string;
  group: string;
  field_name: string;
  unit: string | null;
  object_type: string;
}

async function fetchBulkstatsCatalog(): Promise<BulkstatsCatalogEntry[]> {
  const { data } = await api.get<BulkstatsCatalogEntry[]>('/bulkstats/catalog', { params: { enabled: true } });
  return data;
}

/** Collapse catalog rows down to one dropdown option per metric_name — some
 * metrics (e.g. disc-reason-<N>) are ~600 near-identical catalog rows that
 * all share one metric_name, distinguished only by object_id at query time
 * via the instance picker, not by separate dropdown entries. */
function dedupeCatalogOptions(entries: BulkstatsCatalogEntry[]): Array<{ value: string; label: string }> {
  const byMetric = new Map<string, BulkstatsCatalogEntry[]>();
  for (const entry of entries) {
    const bucket = byMetric.get(entry.metric_name) ?? [];
    bucket.push(entry);
    byMetric.set(entry.metric_name, bucket);
  }
  return Array.from(byMetric.entries()).map(([metricName, rows]) => {
    const [first] = rows;
    const label = rows.length === 1
      ? `StarOS · ${first.group}.${first.field_name}`
      : `StarOS · ${first.group} by ${first.object_type} (${rows.length})`;
    return { value: metricName, label };
  });
}

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
  objectId: string,
): Promise<AggregatePoint[]> {
  const { data } = await api.get<AggregatePoint[]>(
    `/performance/devices/${deviceId}/kpis/aggregate`,
    {
      params: {
        kpi_type: kpiType,
        since: range.since,
        until: range.until,
        bucket: '5m',
        ...(objectId ? { object_id: objectId } : {}),
      },
    },
  );
  return data;
}

export function PerformancePage() {
  const queryClient = useQueryClient();
  const [deviceId, setDeviceId] = useState('');
  const [kpiType, setKpiType] = useState('cpu_5min');
  const [objectId, setObjectId] = useState('');
  const [range, setRange] = useState<TimeRange>(defaultRange);
  const isBulkstatsMetric = kpiType.startsWith(BULKSTATS_PREFIX);

  const summaryQuery = useQuery({
    queryKey: ['performance-summary'],
    queryFn: fetchSummary,
    refetchInterval: 30_000,
  });

  const catalogQuery = useQuery({
    queryKey: ['bulkstats-catalog'],
    queryFn: fetchBulkstatsCatalog,
    staleTime: 60_000,
  });

  const kpiOptions = [
    ...SNMP_KPI_OPTIONS,
    ...dedupeCatalogOptions(catalogQuery.data ?? []),
  ];

  const aggregateQuery = useQuery({
    queryKey: ['performance-aggregate', deviceId, kpiType, range, objectId],
    queryFn: () => fetchAggregate(deviceId, kpiType, range, objectId),
    enabled: Boolean(deviceId),
    refetchInterval: 30_000,
  });

  const handleKpiTypeChange = useCallback((next: string) => {
    setKpiType(next);
    setObjectId('');
  }, []);

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['performance-summary'] });
    if (deviceId) {
      queryClient.invalidateQueries({ queryKey: ['performance-aggregate', deviceId, kpiType, range, objectId] });
    }
  }, [queryClient, deviceId, kpiType, range, objectId]);

  const summary = summaryQuery.data;
  const statItems = [
    { label: 'Average CPU (%)', value: summary ? summary.cpu_avg.toFixed(1) : '—', unit: '%' },
    { label: 'Average memory (%)', value: summary ? summary.mem_avg.toFixed(1) : '—', unit: '%' },
    { label: 'Polling status', value: summaryQuery.isLoading ? 'Polling…' : 'Active', trend: 'neutral' as const },
  ];

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Performance - PENDING FOR TEST"
        subtitle="Network KPIs — Cisco NMS"
        actions={
          <Button variant="outline" size="sm" onClick={handleRefresh} leftIcon={<RefreshCw size={14} />}>
            Refresh
          </Button>
        }
      />

      <Card>
        <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <div className="font-semibold">PENDING FOR TEST</div>
          <p className="mt-1">
            Performance needs at least one reachable device with valid SNMP credentials and collected KPI samples before the charts and summaries can be accepted end-to-end.
          </p>
        </div>
      </Card>

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
              onChange={(e) => handleKpiTypeChange(e.target.value)}
              options={kpiOptions}
            />
          </div>
          {isBulkstatsMetric && deviceId && (
            <div className="flex-1 min-w-48">
              <label className="block text-xs text-gray-500 mb-1">Instance</label>
              <InstancePicker deviceId={deviceId} kpiType={kpiType} value={objectId} onChange={setObjectId} />
            </div>
          )}
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
