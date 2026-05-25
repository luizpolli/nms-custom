import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Activity, DatabaseZap, RadioTower, Route, Send, Waves } from 'lucide-react';
import { useState } from 'react';
import { Badge, Button, Card, EmptyState, InfoFloat, Input, PageHeader, StatCard } from '../../components/ui';
import { api } from '../../lib/api';

type Collector = {
  id: string;
  name: string;
  collector_type: string;
  endpoint?: string | null;
  enabled: boolean;
  status: string;
  last_seen_at?: string | null;
};

type Subscription = {
  id: string;
  name: string;
  path: string;
  collector_id?: string | null;
  device_id?: string | null;
  sample_interval_ms: number;
  mode: string;
  enabled: boolean;
  status: string;
  last_sample_at?: string | null;
};

type SensorPath = {
  id: string;
  vendor: string;
  platform_family?: string | null;
  path: string;
  metric_name: string;
  kpi_type: string;
  unit?: string | null;
  object_type: string;
  enabled: boolean;
};

type TelemetryHealth = {
  collectors: number;
  enabled_collectors: number;
  subscriptions: number;
  enabled_subscriptions: number;
};

const DEFAULT_PATH = '/interfaces/interface/state/counters/in-octets';

const TELEMETRY_HELP = {
  collectors: 'Telemetry collectors receive or poll streaming data from devices. Each collector represents an ingestion endpoint or protocol adapter.',
  enabledCollectors: 'Collectors that are active and expected to accept telemetry samples from the network.',
  subscriptions: 'Configured sensor subscriptions that define which telemetry paths should be sampled.',
  enabledSubscriptions: 'Subscriptions currently enabled for collection and normalization into KPI records.',
  newCollector: 'Create a collector endpoint for a telemetry protocol such as gNMI. The endpoint is optional when the collector is local or discovered externally.',
  newSubscription: 'Create a subscription for a sensor path and sample interval. Subscriptions tell the collector what to collect and how frequently.',
  sensorMapping: 'Map vendor sensor paths into canonical metric names and KPI types so downstream views can compare data consistently.',
  collectorsTable: 'Current telemetry collectors, their protocol type, endpoint, and operational status.',
  subscriptionsTable: 'Current telemetry subscriptions, including sensor path, sample interval, and enabled status.',
  sensorCatalog: 'Catalog of normalized sensor mappings. These mappings translate raw telemetry paths into KPI names, units, and object types.',
  sampleIngestion: 'Raw samples can be posted through the telemetry API; the backend normalizes them and publishes KPI events for other services.',
};

function PanelTitle({ title, description, icon }: { title: string; description: string; icon?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center gap-2">
      {icon}
      <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
      <InfoFloat title={title} description={description} />
    </div>
  );
}

function InfoStatCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="relative">
      {children}
      <div className="absolute right-3 top-3">
        <InfoFloat title={title} description={description} />
      </div>
    </div>
  );
}

export function TelemetryPage() {
  const qc = useQueryClient();
  const [collector, setCollector] = useState({ name: '', collector_type: 'gnmi', endpoint: '' });
  const [subscription, setSubscription] = useState({ name: '', path: DEFAULT_PATH, sample_interval_ms: 60000 });
  const [sensor, setSensor] = useState({
    vendor: 'cisco',
    path: DEFAULT_PATH,
    metric_name: 'interface.in_octets',
    kpi_type: 'if_in_octets',
    unit: 'octets',
    object_type: 'interface',
  });

  const healthQuery = useQuery({ queryKey: ['telemetry-health'], queryFn: () => api.get<TelemetryHealth>('/telemetry/health').then((r) => r.data) });
  const collectorsQuery = useQuery({ queryKey: ['telemetry-collectors'], queryFn: () => api.get<Collector[]>('/telemetry/collectors').then((r) => r.data) });
  const subscriptionsQuery = useQuery({ queryKey: ['telemetry-subscriptions'], queryFn: () => api.get<Subscription[]>('/telemetry/subscriptions').then((r) => r.data) });
  const sensorsQuery = useQuery({ queryKey: ['telemetry-sensor-paths'], queryFn: () => api.get<SensorPath[]>('/telemetry/sensor-paths').then((r) => r.data) });

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ['telemetry-health'] });
    qc.invalidateQueries({ queryKey: ['telemetry-collectors'] });
    qc.invalidateQueries({ queryKey: ['telemetry-subscriptions'] });
    qc.invalidateQueries({ queryKey: ['telemetry-sensor-paths'] });
  };

  const createCollector = useMutation({
    mutationFn: () => api.post('/telemetry/collectors', { ...collector, endpoint: collector.endpoint || null }),
    onSuccess: () => { setCollector({ name: '', collector_type: 'gnmi', endpoint: '' }); refreshAll(); },
  });
  const createSubscription = useMutation({
    mutationFn: () => api.post('/telemetry/subscriptions', subscription),
    onSuccess: () => { setSubscription({ name: '', path: DEFAULT_PATH, sample_interval_ms: 60000 }); refreshAll(); },
  });
  const createSensor = useMutation({
    mutationFn: () => api.post('/telemetry/sensor-paths', sensor),
    onSuccess: () => { refreshAll(); },
  });

  const health = healthQuery.data;
  const collectors = collectorsQuery.data ?? [];
  const subscriptions = subscriptionsQuery.data ?? [];
  const sensors = sensorsQuery.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Telemetry" subtitle="Streaming telemetry collectors, subscriptions, sensor catalog, and ingestion health" />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <InfoStatCard title="Collectors" description={TELEMETRY_HELP.collectors}>
          <StatCard title="Collectors" value={health?.collectors ?? 0} icon={<RadioTower className="h-5 w-5" />} loading={healthQuery.isLoading} />
        </InfoStatCard>
        <InfoStatCard title="Enabled collectors" description={TELEMETRY_HELP.enabledCollectors}>
          <StatCard title="Enabled collectors" value={health?.enabled_collectors ?? 0} icon={<Activity className="h-5 w-5" />} tone="success" loading={healthQuery.isLoading} />
        </InfoStatCard>
        <InfoStatCard title="Subscriptions" description={TELEMETRY_HELP.subscriptions}>
          <StatCard title="Subscriptions" value={health?.subscriptions ?? 0} icon={<Route className="h-5 w-5" />} loading={healthQuery.isLoading} />
        </InfoStatCard>
        <InfoStatCard title="Enabled subscriptions" description={TELEMETRY_HELP.enabledSubscriptions}>
          <StatCard title="Enabled subscriptions" value={health?.enabled_subscriptions ?? 0} icon={<Waves className="h-5 w-5" />} tone="success" loading={healthQuery.isLoading} />
        </InfoStatCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="p-4">
          <PanelTitle title="New collector" description={TELEMETRY_HELP.newCollector} />
          <div className="space-y-3">
            <Input label="Name" value={collector.name} onChange={(e) => setCollector((p) => ({ ...p, name: e.target.value }))} />
            <Input label="Type" value={collector.collector_type} onChange={(e) => setCollector((p) => ({ ...p, collector_type: e.target.value }))} />
            <Input label="Endpoint" value={collector.endpoint} onChange={(e) => setCollector((p) => ({ ...p, endpoint: e.target.value }))} placeholder="gnmi://10.0.0.10:57400" />
            <Button onClick={() => createCollector.mutate()} disabled={!collector.name || createCollector.isPending}>Create collector</Button>
          </div>
        </Card>

        <Card className="p-4">
          <PanelTitle title="New subscription" description={TELEMETRY_HELP.newSubscription} />
          <div className="space-y-3">
            <Input label="Name" value={subscription.name} onChange={(e) => setSubscription((p) => ({ ...p, name: e.target.value }))} />
            <Input label="Sensor path" value={subscription.path} onChange={(e) => setSubscription((p) => ({ ...p, path: e.target.value }))} />
            <Input label="Sample interval ms" type="number" value={subscription.sample_interval_ms} onChange={(e) => setSubscription((p) => ({ ...p, sample_interval_ms: Number(e.target.value) }))} />
            <Button onClick={() => createSubscription.mutate()} disabled={!subscription.name || !subscription.path || createSubscription.isPending}>Create subscription</Button>
          </div>
        </Card>

        <Card className="p-4">
          <PanelTitle title="Sensor path mapping" description={TELEMETRY_HELP.sensorMapping} />
          <div className="space-y-3">
            <Input label="Path" value={sensor.path} onChange={(e) => setSensor((p) => ({ ...p, path: e.target.value }))} />
            <Input label="Metric name" value={sensor.metric_name} onChange={(e) => setSensor((p) => ({ ...p, metric_name: e.target.value }))} />
            <Input label="KPI type" value={sensor.kpi_type} onChange={(e) => setSensor((p) => ({ ...p, kpi_type: e.target.value }))} />
            <div className="grid grid-cols-2 gap-2">
              <Input label="Unit" value={sensor.unit} onChange={(e) => setSensor((p) => ({ ...p, unit: e.target.value }))} />
              <Input label="Object type" value={sensor.object_type} onChange={(e) => setSensor((p) => ({ ...p, object_type: e.target.value }))} />
            </div>
            <Button onClick={() => createSensor.mutate()} disabled={!sensor.path || !sensor.metric_name || !sensor.kpi_type || createSensor.isPending}>Save mapping</Button>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <TelemetryTable
          title="Collectors"
          description={TELEMETRY_HELP.collectorsTable}
          empty="No telemetry collectors yet"
          rows={collectors.map((c) => [c.name, c.collector_type, c.endpoint || '—', <Badge key={c.id} variant={c.enabled ? 'success' : 'default'}>{c.status || (c.enabled ? 'enabled' : 'disabled')}</Badge>])}
        />
        <TelemetryTable
          title="Subscriptions"
          description={TELEMETRY_HELP.subscriptionsTable}
          empty="No telemetry subscriptions yet"
          rows={subscriptions.map((s) => [s.name, s.path, `${s.sample_interval_ms}ms`, <Badge key={s.id} variant={s.enabled ? 'success' : 'default'}>{s.status}</Badge>])}
        />
      </div>

      <Card className="p-4">
        <PanelTitle title="Sensor path catalog" description={TELEMETRY_HELP.sensorCatalog} icon={<DatabaseZap className="h-5 w-5 text-cisco-blue" />} />
        {sensors.length === 0 ? <EmptyState title="No sensor paths" description="Create mappings so telemetry samples normalize into canonical KPI names." /> : (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800"><tr><Th>Path</Th><Th>Metric</Th><Th>KPI type</Th><Th>Unit</Th><Th>Status</Th></tr></thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">{sensors.map((s) => <tr key={s.id}><Td>{s.path}</Td><Td>{s.metric_name}</Td><Td>{s.kpi_type}</Td><Td>{s.unit || '—'}</Td><Td><Badge variant={s.enabled ? 'success' : 'default'}>{s.enabled ? 'enabled' : 'disabled'}</Badge></Td></tr>)}</tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="p-4">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          <Send className="h-4 w-4" />
          <span>Samples can be posted to <code className="rounded bg-gray-100 px-1 dark:bg-gray-800">POST /api/telemetry/samples</code>; normalized KPI rows and Redis Stream events are created by the backend.</span>
          <InfoFloat title="Sample ingestion" description={TELEMETRY_HELP.sampleIngestion} />
        </div>
      </Card>
    </div>
  );
}

function TelemetryTable({ title, description, empty, rows }: { title: string; description: string; empty: string; rows: Array<Array<React.ReactNode>> }) {
  return <Card className="p-4"><PanelTitle title={title} description={description} />{rows.length === 0 ? <EmptyState title={empty} /> : <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700"><table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700"><tbody className="divide-y divide-gray-100 dark:divide-gray-800">{rows.map((row, idx) => <tr key={idx}>{row.map((cell, i) => <Td key={i}>{cell}</Td>)}</tr>)}</tbody></table></div>}</Card>;
}
function Th({ children }: { children: React.ReactNode }) { return <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">{children}</th>; }
function Td({ children }: { children: React.ReactNode }) { return <td className="px-3 py-2 align-top text-gray-700 dark:text-gray-200">{children}</td>; }

export default TelemetryPage;
