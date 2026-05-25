import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Columns3, Download, Globe2, History, ListFilter, Save, Trash2 } from 'lucide-react';
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
  clear: number;
}

interface AlarmFilters {
  q: string;
  severity: string;
  state: string;
  device_id: string;
  object_type: string;
  object_id: string;
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
  object_type: '',
  object_id: '',
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

function alarmExportParams(filters: AlarmFilters, alarmIds?: string[]): URLSearchParams {
  const params = new URLSearchParams({ format: 'csv' });
  if (alarmIds?.length) {
    alarmIds.forEach((id) => params.append('alarm_ids', id));
    return params;
  }
  Object.entries(filters).forEach(([key, value]) => {
    if (key === 'limit' || key === 'offset') return;
    if (value !== '' && value !== 0) params.append(key, String(value));
  });
  return params;
}

async function exportAlarmCsv(filters: AlarmFilters, alarmIds?: string[]) {
  const params = alarmExportParams(filters, alarmIds);
  const response = await api.get(`/alarms/export?${params.toString()}`, {
    responseType: 'blob',
  });
  const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = alarmIds?.length ? 'alarms_selected_export.csv' : 'alarms_export.csv';
  a.click();
  URL.revokeObjectURL(url);
}

function isoToLocalInput(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function localDateTimeToIso(value: string): string {
  if (!value) return '';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '' : d.toISOString();
}

function todayDateInput(): string {
  return isoToLocalInput(new Date().toISOString()).slice(0, 10);
}

const TIME_OPTIONS = Array.from({ length: 96 }, (_, index) => {
  const hours = String(Math.floor(index / 4)).padStart(2, '0');
  const minutes = String((index % 4) * 15).padStart(2, '0');
  const value = `${hours}:${minutes}`;
  return { value, label: value };
});

interface DateTimeFilterInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
}

function DateTimeFilterInput({ label, value, onChange }: DateTimeFilterInputProps) {
  const localValue = isoToLocalInput(value);
  const dateValue = localValue.slice(0, 10);
  const timeValue = localValue.slice(11, 16);
  const timeOptions = timeValue && !TIME_OPTIONS.some((option) => option.value === timeValue)
    ? [{ value: timeValue, label: timeValue }, ...TIME_OPTIONS]
    : TIME_OPTIONS;

  function update(nextDate: string, nextTime: string) {
    if (!nextDate && !nextTime) {
      onChange('');
      return;
    }
    const resolvedDate = nextDate || todayDateInput();
    const resolvedTime = nextTime || '00:00';
    onChange(localDateTimeToIso(`${resolvedDate}T${resolvedTime}`));
  }

  return (
    <div className="flex-1 min-w-[17rem]">
      <label className="block text-xs text-gray-500 mb-1">{label}</label>
      <div className="grid grid-cols-[minmax(0,1fr)_6.5rem] gap-2">
        <input
          type="date"
          value={dateValue}
          onChange={(e) => update(e.target.value, timeValue)}
          className="w-full text-xs border rounded px-2 py-1.5 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 border-gray-300"
          aria-label={`${label} date`}
        />
        <Select
          value={timeValue}
          onChange={(e) => update(dateValue, e.target.value)}
          options={[{ value: '', label: 'Time' }, ...timeOptions]}
          className="w-full py-1.5 px-2 text-xs"
          aria-label={`${label} time`}
        />
      </div>
    </div>
  );
}

export function AlarmsPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const queryString = searchParams.toString();
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
  const [exportScope, setExportScope] = useState<'all' | 'selected' | null>(null);
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

  useEffect(() => {
    const params = new URLSearchParams(queryString);
    const deviceId = params.get('device_id') ?? '';
    const objectType = params.get('object_type') ?? '';
    const objectId = params.get('object_id') ?? '';
    if (!deviceId && !objectType && !objectId) return;
    setFilters((prev) => ({
      ...prev,
      device_id: deviceId || prev.device_id,
      object_type: objectType || prev.object_type,
      object_id: objectId || prev.object_id,
      offset: 0,
    }));
  }, [queryString]);

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
    filters.object_type,
    filters.object_id,
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

  async function handleExportAll() {
    setExportScope('all');
    try {
      await exportAlarmCsv(filters);
    } finally {
      setExportScope(null);
    }
  }

  async function handleExportSelected() {
    const alarmIds = Array.from(selectedAlarmIds);
    if (alarmIds.length === 0) return;
    setExportScope('selected');
    try {
      await exportAlarmCsv(filters, alarmIds);
    } finally {
      setExportScope(null);
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
      <PageHeader
        title="Alarms"
        subtitle="Real-time monitoring — Cisco NMS"
        actions={
          <Link
            to="/alarms/history"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            <History className="h-4 w-4" />
            History
          </Link>
        }
      />

      {summary && (
        <Card>
          <AlarmSummaryStrip
            summary={summary}
            activeSeverity={filters.severity}
            onSelect={(sev) => setFilters((prev) => ({
              ...prev,
              severity: prev.severity === sev ? '' : sev,
              offset: 0,
            }))}
          />
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
              label="Object type"
              value={filters.object_type}
              onChange={(e) => setFilter('object_type', e.target.value)}
              placeholder="interface"
              className="py-1.5 text-xs"
            />
          </div>
          <div className="flex-1 min-w-44">
            <Input
              label="Object ID"
              value={filters.object_id}
              onChange={(e) => setFilter('object_id', e.target.value)}
              placeholder="interface UUID"
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
          <DateTimeFilterInput label="From" value={filters.since} onChange={(value) => setFilter('since', value)} />
          <DateTimeFilterInput label="To" value={filters.until} onChange={(value) => setFilter('until', value)} />
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
          <Button
            size="sm"
            variant="outline"
            leftIcon={<Download className="h-4 w-4" />}
            onClick={handleExportAll}
            loading={exportScope === 'all'}
          >
            Export All
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
          <Button
            size="sm"
            variant="outline"
            leftIcon={<Download className="h-4 w-4" />}
            onClick={handleExportSelected}
            loading={exportScope === 'selected'}
          >
            Export Selected
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
