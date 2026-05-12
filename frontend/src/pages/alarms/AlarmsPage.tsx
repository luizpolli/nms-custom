import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { PageHeader, Card, Select, Button } from '../../components/ui';
import { api } from '../../lib/api';
import { useAlarmWebSocket } from '../../lib/ws';
import { AlarmSummaryStrip } from './components/AlarmSummaryStrip';
import { AlarmTable, Alarm } from './components/AlarmTable';
import { AlarmDetailDrawer } from './components/AlarmDetailDrawer';
import { AlarmAckModal } from './components/AlarmAckModal';

interface AlarmSummary {
  critical: number;
  major: number;
  minor: number;
  warning: number;
  info: number;
}

interface AlarmFilters {
  severity: string;
  state: string;
  device_id: string;
  since: string;
  until: string;
  limit: number;
}

const DEFAULT_FILTERS: AlarmFilters = {
  severity: '',
  state: '',
  device_id: '',
  since: '',
  until: '',
  limit: 100,
};

async function fetchAlarms(filters: AlarmFilters): Promise<Alarm[]> {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v !== '' && v !== 0),
  );
  const { data } = await api.get<Alarm[]>('/alarms', { params });
  return data;
}

async function fetchAlarmSummary(): Promise<AlarmSummary> {
  const { data } = await api.get<AlarmSummary>('/alarms/summary');
  return data;
}

async function clearAlarm(id: string): Promise<void> {
  await api.post(`/alarms/${id}/clear`);
}

export function AlarmsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<AlarmFilters>(DEFAULT_FILTERS);
  const [selectedAlarm, setSelectedAlarm] = useState<Alarm | null>(null);
  const [ackAlarmId, setAckAlarmId] = useState<string | null>(null);

  const filtersKey = [filters.severity, filters.state, filters.device_id, filters.since, filters.until, filters.limit];

  const alarmsQuery = useQuery({
    queryKey: ['alarms', ...filtersKey],
    queryFn: () => fetchAlarms(filters),
    refetchInterval: 30_000,
  });

  const summaryQuery = useQuery({
    queryKey: ['alarms-summary'],
    queryFn: fetchAlarmSummary,
    refetchInterval: 30_000,
  });

  useAlarmWebSocket((event) => {
    if (event.type === 'hb') return;
    const newAlarm = event as unknown as Alarm;
    queryClient.setQueryData<Alarm[]>(['alarms', ...filtersKey], (old = []) => [
      { ...newAlarm, _flash: true },
      ...old,
    ]);
    queryClient.invalidateQueries({ queryKey: ['alarms-summary'] });

    setTimeout(() => {
      queryClient.setQueryData<Alarm[]>(['alarms', ...filtersKey], (old = []) =>
        old.map((a) => (a.id === newAlarm.id ? { ...a, _flash: false } : a)),
      );
    }, 2000);
  });

  function setFilter(key: keyof AlarmFilters, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  async function handleClear(id: string) {
    await clearAlarm(id);
    queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
    queryClient.invalidateQueries({ queryKey: ['alarms-summary'] });
    if (selectedAlarm?.id === id) setSelectedAlarm(null);
  }

  const alarms = alarmsQuery.data ?? [];
  const summary = summaryQuery.data;

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Alarms" subtitle="Real-time monitoring — Cisco NMS" />

      {summary && (
        <Card>
          <AlarmSummaryStrip summary={summary} />
        </Card>
      )}

      <Card>
        <div className="flex flex-wrap gap-3 items-end mb-4">
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">Severity</label>
            <Select
              value={filters.severity}
              onChange={(e) => setFilter('severity', e.target.value)}
              options={[
                { value: '', label: 'All' },
                { value: 'critical', label: 'Critical' },
                { value: 'major', label: 'Major' },
                { value: 'minor', label: 'Minor' },
                { value: 'warning', label: 'Warning' },
                { value: 'info', label: 'Info' },
              ]}
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">State</label>
            <Select
              value={filters.state}
              onChange={(e) => setFilter('state', e.target.value)}
              options={[
                { value: '', label: 'All' },
                { value: 'active', label: 'Active' },
                { value: 'acknowledged', label: 'Acknowledged' },
                { value: 'cleared', label: 'Cleared' },
              ]}
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">From</label>
            <input
              type="datetime-local"
              value={filters.since}
              onChange={(e) => setFilter('since', e.target.value ? new Date(e.target.value).toISOString() : '')}
              className="w-full text-xs border rounded px-2 py-1.5 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 border-gray-300"
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">To</label>
            <input
              type="datetime-local"
              value={filters.until}
              onChange={(e) => setFilter('until', e.target.value ? new Date(e.target.value).toISOString() : '')}
              className="w-full text-xs border rounded px-2 py-1.5 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 border-gray-300"
            />
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setFilters(DEFAULT_FILTERS)}
          >
            Clear filters
          </Button>
        </div>

        {alarmsQuery.isLoading && (
          <p className="text-sm text-gray-400 text-center py-8">Loading alarms…</p>
        )}
        {alarmsQuery.isError && (
          <p className="text-sm text-red-500 text-center py-8">Failed to load alarms.</p>
        )}
        {!alarmsQuery.isLoading && !alarmsQuery.isError && (
          <AlarmTable
            alarms={alarms}
            onView={setSelectedAlarm}
            onAck={setAckAlarmId}
            onClear={handleClear}
          />
        )}
      </Card>

      {selectedAlarm && (
        <AlarmDetailDrawer
          alarm={selectedAlarm}
          filtersKey={filtersKey}
          onClose={() => setSelectedAlarm(null)}
          onAck={(id) => { setSelectedAlarm(null); setAckAlarmId(id); }}
        />
      )}

      {ackAlarmId && (
        <AlarmAckModal
          alarmId={ackAlarmId}
          filtersKey={filtersKey}
          onClose={() => setAckAlarmId(null)}
        />
      )}
    </div>
  );
}
