import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Columns3, Globe2, ListFilter, Save, Trash2 } from 'lucide-react';
import { PageHeader, Card, Select, Button, Input, Modal } from '../../components/ui';
import { api } from '../../lib/api';
import { useAlarmWebSocket } from '../../lib/ws';
import { AlarmSummaryStrip } from './components/AlarmSummaryStrip';
import { AlarmTable, Alarm, AlarmColumnKey, ALARM_COLUMNS, DEFAULT_VISIBLE_COLUMNS } from './components/AlarmTable';
import { AlarmDetailDrawer } from './components/AlarmDetailDrawer';
import { AlarmAckModal } from './components/AlarmAckModal';
import { AlarmSuppressModal } from './components/AlarmSuppressModal';

interface AlarmSummary {
  critical: number;
  major: number;
  minor: number;
  warning: number;
  info: number;
}

interface AlarmFilters {
  q: string;
  severity: string;
  state: string;
  device_id: string;
  category: string;
  event_type: string;
  source_host: string;
  since: string;
  until: string;
  limit: number;
  offset: number;
}

const DEFAULT_FILTERS: AlarmFilters = {
  q: '',
  severity: '',
  state: '',
  device_id: '',
  category: '',
  event_type: '',
  source_host: '',
  since: '',
  until: '',
  limit: 100,
  offset: 0,
};

interface SavedAlarmFilter {
  id: string;
  name: string;
  owner: string;
  is_public: boolean;
  filters: Partial<AlarmFilters>;
  created_at: string;
  updated_at: string;
  can_update: boolean;
  can_delete: boolean;
}

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

async function fetchSavedFilters(): Promise<SavedAlarmFilter[]> {
  const { data } = await api.get<SavedAlarmFilter[]>('/alarms/filters');
  return data;
}

async function saveAlarmFilter(name: string, isPublic: boolean, filters: AlarmFilters): Promise<SavedAlarmFilter> {
  const { data } = await api.post<SavedAlarmFilter>('/alarms/filters', {
    name,
    is_public: isPublic,
    filters,
  });
  return data;
}

async function deleteAlarmFilter(id: string): Promise<void> {
  await api.delete(`/alarms/filters/${id}`);
}

async function publishAlarmFilter(id: string): Promise<SavedAlarmFilter> {
  const { data } = await api.patch<SavedAlarmFilter>(`/alarms/filters/${id}`, { is_public: true });
  return data;
}

async function clearAlarm(id: string): Promise<void> {
  await api.post(`/alarms/${id}/clear`);
}

async function bulkAckAlarms(alarmIds: string[]): Promise<void> {
  await api.post('/alarms/bulk-ack', { alarm_ids: alarmIds, by_user: 'operator' });
}

async function bulkClearAlarms(alarmIds: string[]): Promise<void> {
  await api.post('/alarms/bulk-clear', { alarm_ids: alarmIds });
}

async function unsuppressAlarm(id: string): Promise<void> {
  await api.post(`/alarms/${id}/unsuppress`, { by_user: 'operator' });
}

function isoToLocalInput(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function AlarmsPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<AlarmFilters>(DEFAULT_FILTERS);
  const [selectedAlarm, setSelectedAlarm] = useState<Alarm | null>(null);
  const [ackAlarmId, setAckAlarmId] = useState<string | null>(null);
  const [suppressAlarmId, setSuppressAlarmId] = useState<string | null>(null);
  const [saveFilterOpen, setSaveFilterOpen] = useState(false);
  const [loadFilterOpen, setLoadFilterOpen] = useState(false);
  const [filterName, setFilterName] = useState('');
  const [filterIsPublic, setFilterIsPublic] = useState(false);
  const [savingFilter, setSavingFilter] = useState(false);
  const [selectedAlarmIds, setSelectedAlarmIds] = useState<Set<string>>(new Set());
  const [bulkAction, setBulkAction] = useState<'ack' | 'clear' | null>(null);
  const [activeSavedFilter, setActiveSavedFilter] = useState<SavedAlarmFilter | null>(null);
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Set<AlarmColumnKey>>(() => {
    try {
      const raw = localStorage.getItem('alarms.visibleColumns');
      if (raw) {
        const parsed = JSON.parse(raw) as AlarmColumnKey[];
        return new Set(parsed.filter((k) => ALARM_COLUMNS.some((c) => c.key === k)));
      }
    } catch { /* ignore */ }
    return new Set(DEFAULT_VISIBLE_COLUMNS);
  });

  function toggleColumn(key: AlarmColumnKey) {
    setVisibleColumns((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      try { localStorage.setItem('alarms.visibleColumns', JSON.stringify([...next])); } catch { /* ignore */ }
      return next;
    });
  }

  const filtersKey = [
    filters.q,
    filters.severity,
    filters.state,
    filters.device_id,
    filters.category,
    filters.event_type,
    filters.source_host,
    filters.since,
    filters.until,
    filters.limit,
    filters.offset,
  ];

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

  const savedFiltersQuery = useQuery({
    queryKey: ['alarm-filters'],
    queryFn: fetchSavedFilters,
    retry: false,
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

  function setFilter(key: keyof AlarmFilters, value: string | number) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function applySavedFilter(savedFilter: SavedAlarmFilter) {
    setFilters({
      ...DEFAULT_FILTERS,
      ...savedFilter.filters,
      limit: Number(savedFilter.filters.limit ?? DEFAULT_FILTERS.limit),
      offset: Number(savedFilter.filters.offset ?? DEFAULT_FILTERS.offset),
    });
    setActiveSavedFilter(savedFilter);
    setLoadFilterOpen(false);
  }

  async function handleSaveFilter() {
    const name = filterName.trim();
    if (!name) return;
    setSavingFilter(true);
    try {
      await saveAlarmFilter(name, filterIsPublic, filters);
      await queryClient.invalidateQueries({ queryKey: ['alarm-filters'] });
      setFilterName('');
      setFilterIsPublic(false);
      setActiveSavedFilter(null);
      setSaveFilterOpen(false);
    } finally {
      setSavingFilter(false);
    }
  }

  async function handleDeleteFilter(id: string) {
    await deleteAlarmFilter(id);
    await queryClient.invalidateQueries({ queryKey: ['alarm-filters'] });
  }

  async function handlePublishFilter(id: string) {
    await publishAlarmFilter(id);
    await queryClient.invalidateQueries({ queryKey: ['alarm-filters'] });
  }

  async function handleClear(id: string) {
    await clearAlarm(id);
    queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
    queryClient.invalidateQueries({ queryKey: ['alarms-summary'] });
    queryClient.invalidateQueries({ queryKey: ['assurance-summary'] });
    if (selectedAlarm?.id === id) setSelectedAlarm(null);
  }

  async function invalidateAlarmViews() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['alarms'] }),
      queryClient.invalidateQueries({ queryKey: ['alarms-summary'] }),
      queryClient.invalidateQueries({ queryKey: ['assurance'] }),
      queryClient.invalidateQueries({ queryKey: ['assurance-summary'] }),
    ]);
  }

  async function handleBulkAck() {
    const alarmIds = Array.from(selectedAlarmIds);
    if (alarmIds.length === 0) return;
    setBulkAction('ack');
    try {
      await bulkAckAlarms(alarmIds);
      setSelectedAlarmIds(new Set());
      await invalidateAlarmViews();
    } finally {
      setBulkAction(null);
    }
  }

  async function handleBulkClear() {
    const alarmIds = Array.from(selectedAlarmIds);
    if (alarmIds.length === 0) return;
    setBulkAction('clear');
    try {
      await bulkClearAlarms(alarmIds);
      setSelectedAlarmIds(new Set());
      await invalidateAlarmViews();
      if (selectedAlarm && selectedAlarmIds.has(selectedAlarm.id)) setSelectedAlarm(null);
    } finally {
      setBulkAction(null);
    }
  }

  async function handleUnsuppress(id: string) {
    await unsuppressAlarm(id);
    queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
    queryClient.invalidateQueries({ queryKey: ['alarms-summary'] });
    queryClient.invalidateQueries({ queryKey: ['assurance-summary'] });
    if (selectedAlarm?.id === id) setSelectedAlarm(null);
  }

  const alarms = alarmsQuery.data ?? [];
  const summary = summaryQuery.data;
  const saveNameMatchesReadOnlyPublic =
    Boolean(activeSavedFilter?.is_public && !activeSavedFilter.can_update && filterName.trim() === activeSavedFilter.name);

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
          <div className="flex-[2] min-w-56">
            <Input
              label="Search"
              value={filters.q}
              onChange={(e) => setFilter('q', e.target.value)}
              placeholder="Message, source, event, category, correlation"
              className="py-1.5 text-xs"
            />
          </div>
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
                { value: 'suppressed', label: 'Suppressed' },
              ]}
            />
          </div>
          <div className="flex-1 min-w-36">
            <Input
              label="Category"
              value={filters.category}
              onChange={(e) => setFilter('category', e.target.value)}
              placeholder="link"
              className="py-1.5 text-xs"
            />
          </div>
          <div className="flex-1 min-w-36">
            <Input
              label="Source host"
              value={filters.source_host}
              onChange={(e) => setFilter('source_host', e.target.value)}
              placeholder="router01"
              className="py-1.5 text-xs"
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">From</label>
            <input
              type="datetime-local"
              step={60}
              value={isoToLocalInput(filters.since)}
              onChange={(e) => setFilter('since', e.target.value ? new Date(e.target.value).toISOString() : '')}
              className="w-full text-xs border rounded px-2 py-1.5 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 border-gray-300"
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-xs text-gray-500 mb-1">To</label>
            <input
              type="datetime-local"
              step={60}
              value={isoToLocalInput(filters.until)}
              onChange={(e) => setFilter('until', e.target.value ? new Date(e.target.value).toISOString() : '')}
              className="w-full text-xs border rounded px-2 py-1.5 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 border-gray-300"
            />
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setFilters(DEFAULT_FILTERS);
              setSelectedAlarmIds(new Set());
              setActiveSavedFilter(null);
            }}
          >
            Clear filters
          </Button>
          <div className="relative">
            <Button
              size="sm"
              variant="outline"
              leftIcon={<Columns3 className="h-4 w-4" />}
              onClick={() => setColumnsOpen((open) => !open)}
            >
              Columns
            </Button>
            {columnsOpen && (
              <div className="absolute right-0 z-20 mt-2 w-56 rounded-md border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-700 dark:bg-gray-900">
                {ALARM_COLUMNS.map((col) => (
                  <label
                    key={col.key}
                    className="flex items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
                  >
                    <input
                      type="checkbox"
                      checked={visibleColumns.has(col.key)}
                      onChange={() => toggleColumn(col.key)}
                      className="rounded border-gray-300"
                    />
                    {col.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <Button
            size="sm"
            variant="outline"
            leftIcon={<Save className="h-4 w-4" />}
            onClick={() => setSaveFilterOpen(true)}
          >
            Save Filter
          </Button>
          <div className="relative">
            <Button
              size="sm"
              variant="outline"
              leftIcon={<ListFilter className="h-4 w-4" />}
              onClick={() => setLoadFilterOpen((open) => !open)}
            >
              Load Filter
            </Button>
            {loadFilterOpen && (
              <div className="absolute right-0 z-20 mt-2 w-72 rounded-md border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-900">
                {savedFiltersQuery.isLoading && (
                  <div className="px-3 py-2 text-sm text-gray-500">Loading filters...</div>
                )}
                {!savedFiltersQuery.isLoading && (savedFiltersQuery.data ?? []).length === 0 && (
                  <div className="px-3 py-2 text-sm text-gray-500">No saved filters</div>
                )}
                {(savedFiltersQuery.data ?? []).map((savedFilter) => (
                    <div
                      key={savedFilter.id}
                      className="flex items-center gap-2 border-b border-gray-100 px-2 py-1 last:border-b-0 dark:border-gray-800"
                    >
                      <button
                        type="button"
                        onClick={() => applySavedFilter(savedFilter)}
                        className="min-w-0 flex-1 rounded px-2 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-800"
                      >
                        <span className="block truncate">{savedFilter.name}</span>
                        <span className="block truncate text-xs text-gray-400">
                          {savedFilter.is_public ? 'Public' : 'Private'} · {savedFilter.owner}
                        </span>
                      </button>
                      {!savedFilter.is_public && savedFilter.can_update && (
                        <button
                          type="button"
                          title="Make public"
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePublishFilter(savedFilter.id);
                          }}
                          className="rounded p-1.5 hover:bg-blue-50 dark:hover:bg-blue-950"
                        >
                          <Globe2 className="h-4 w-4 text-blue-500" />
                        </button>
                      )}
                      {savedFilter.can_delete && (
                        <button
                          type="button"
                          title="Delete filter"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteFilter(savedFilter.id);
                          }}
                          className="rounded p-1.5 hover:bg-red-50 dark:hover:bg-red-950"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </button>
                      )}
                    </div>
                ))}
              </div>
            )}
          </div>
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
            selectedIds={selectedAlarmIds}
            onSelectionChange={setSelectedAlarmIds}
            onView={setSelectedAlarm}
            onAck={setAckAlarmId}
            onClear={handleClear}
            onSuppress={setSuppressAlarmId}
            onUnsuppress={handleUnsuppress}
            visibleColumns={visibleColumns}
          />
        )}
      </Card>

      {selectedAlarmIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3 rounded-lg border border-gray-200 bg-white px-4 py-3 shadow-lg dark:border-gray-700 dark:bg-gray-900">
          <span className="whitespace-nowrap text-sm font-medium text-gray-700 dark:text-gray-200">
            {selectedAlarmIds.size} selected
          </span>
          <Button size="sm" variant="outline" onClick={handleBulkAck} loading={bulkAction === 'ack'}>
            Ack Selected
          </Button>
          <Button size="sm" variant="success" onClick={handleBulkClear} loading={bulkAction === 'clear'}>
            Clear Selected
          </Button>
        </div>
      )}

      {selectedAlarm && (
        <AlarmDetailDrawer
          alarm={selectedAlarm}
          filtersKey={filtersKey}
          onClose={() => setSelectedAlarm(null)}
          onAck={(id) => { setSelectedAlarm(null); setAckAlarmId(id); }}
          onSuppress={(id) => { setSelectedAlarm(null); setSuppressAlarmId(id); }}
          onUnsuppress={handleUnsuppress}
        />
      )}

      {ackAlarmId && (
        <AlarmAckModal
          alarmId={ackAlarmId}
          filtersKey={filtersKey}
          onClose={() => setAckAlarmId(null)}
        />
      )}

      {suppressAlarmId && (
        <AlarmSuppressModal
          alarmId={suppressAlarmId}
          filtersKey={filtersKey}
          onClose={() => setSuppressAlarmId(null)}
        />
      )}

      <Modal open={saveFilterOpen} onClose={() => setSaveFilterOpen(false)} title="Save alarm filter">
        <div className="space-y-4">
          <Input
            label="Filter name"
            value={filterName}
            onChange={(e) => setFilterName(e.target.value)}
            placeholder="Core critical alarms"
          />
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={filterIsPublic}
              onChange={(e) => setFilterIsPublic(e.target.checked)}
              className="rounded border-gray-300"
            />
            Public filter
          </label>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            If unchecked, this filter is saved as private. Public filters can be loaded by other users, but only the owner can update them; other users must save changes as a new filter name.
          </p>
          {activeSavedFilter?.is_public && !activeSavedFilter.can_update && (
            <p className="text-xs text-blue-600 dark:text-blue-400">
              Loaded public filter: {activeSavedFilter.name}. Save your changes with a different name to keep the shared filter unchanged.
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setSaveFilterOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveFilter} loading={savingFilter} disabled={!filterName.trim() || saveNameMatchesReadOnlyPublic}>
              Save
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
