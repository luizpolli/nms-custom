import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ChevronDown, ChevronRight } from 'lucide-react';
import { PageHeader, Card, Select, Input, Button, Badge } from '../../components/ui';
import { api } from '../../lib/api';
import type { AlarmSeverity } from '../../lib/types';

interface AlarmRow {
  id: string;
  severity: string;
  state: string;
  source_host: string;
  event_type: string;
  message: string;
  first_seen: string;
  last_seen: string;
  cleared_at?: string | null;
  acknowledged_by?: string | null;
  raw_varbinds?: Record<string, unknown> | null;
}

interface HistoryEntry {
  id: string;
  timestamp: string;
  actor: string | null;
  action: string;
  outcome: string;
  message: string | null;
  details: Record<string, unknown> | null;
}

const SEVERITIES = new Set(['critical', 'major', 'minor', 'warning', 'info', 'clear']);

function sevVariant(s: string): AlarmSeverity | 'default' {
  return SEVERITIES.has(s) ? (s as AlarmSeverity) : 'default';
}

async function fetchHistoryAlarms(params: Record<string, string | number>): Promise<AlarmRow[]> {
  const { data } = await api.get<AlarmRow[]>('/alarms', { params });
  return data;
}

async function fetchAlarmHistory(id: string): Promise<HistoryEntry[]> {
  const { data } = await api.get<HistoryEntry[]>(`/alarms/${id}/history`);
  return data;
}

function fmt(ts?: string | null) {
  if (!ts) return '—';
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString('en-US');
}

function actionLabel(action: string): string {
  return action.replace(/^alarm\./, '').replace(/_/g, ' ');
}

function actionColor(action: string): string {
  if (action.includes('clear')) return 'text-green-600 dark:text-green-400';
  if (action.includes('acknowledge')) return 'text-blue-600 dark:text-blue-400';
  if (action.includes('suppress')) return 'text-amber-600 dark:text-amber-400';
  return 'text-gray-600 dark:text-gray-400';
}

interface HistoryRowProps {
  alarm: AlarmRow;
  expanded: boolean;
  onToggle: () => void;
}

function HistoryRow({ alarm, expanded, onToggle }: HistoryRowProps) {
  const historyQuery = useQuery({
    queryKey: ['alarm-history', alarm.id],
    queryFn: () => fetchAlarmHistory(alarm.id),
    enabled: expanded,
  });
  const entries = historyQuery.data ?? [];
  const suppression = (alarm.raw_varbinds?._suppression ?? null) as
    | { by?: string; reason?: string; suppressed_at?: string }
    | null;

  return (
    <>
      <tr className="border-t border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50">
        <td className="px-3 py-2">
          <button type="button" onClick={onToggle} aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>
        </td>
        <td className="px-3 py-2">
          <Badge variant={sevVariant(alarm.severity)}>{alarm.severity}</Badge>
        </td>
        <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">{alarm.state}</td>
        <td className="px-3 py-2 font-mono text-xs">{alarm.source_host}</td>
        <td className="px-3 py-2 text-xs">{alarm.event_type}</td>
        <td className="px-3 py-2 max-w-xs truncate text-xs text-gray-700 dark:text-gray-300" title={alarm.message}>
          {alarm.message}
        </td>
        <td className="px-3 py-2 text-xs text-gray-500">{fmt(alarm.first_seen)}</td>
        <td className="px-3 py-2 text-xs text-gray-500">{fmt(alarm.cleared_at)}</td>
        <td className="px-3 py-2 text-xs">{alarm.acknowledged_by ?? suppression?.by ?? '—'}</td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 dark:bg-gray-800/30">
          <td colSpan={9} className="px-6 py-3">
            {historyQuery.isLoading && (
              <p className="text-xs text-gray-500">Loading history…</p>
            )}
            {historyQuery.isError && (
              <p className="text-xs text-red-500">Failed to load history.</p>
            )}
            {!historyQuery.isLoading && entries.length === 0 && (
              <p className="text-xs text-gray-500">No history entries.</p>
            )}
            {entries.length > 0 && (
              <ol className="space-y-1.5">
                {entries.map((e) => (
                  <li key={e.id} className="text-xs">
                    <span className="text-gray-500">{fmt(e.timestamp)}</span>
                    {' · '}
                    <span className={`font-semibold ${actionColor(e.action)}`}>{actionLabel(e.action)}</span>
                    {e.actor && (
                      <>
                        {' by '}
                        <span className="font-mono">{e.actor}</span>
                      </>
                    )}
                    {e.message && (
                      <>
                        {' — '}
                        <span className="text-gray-700 dark:text-gray-300">{e.message}</span>
                      </>
                    )}
                    {e.details && Object.keys(e.details).filter((k) => !['alarm_id', 'correlation_key'].includes(k)).length > 0 && (
                      <pre className="mt-1 inline-block rounded bg-white px-2 py-1 text-[10px] text-gray-600 dark:bg-gray-900 dark:text-gray-400">
                        {JSON.stringify(
                          Object.fromEntries(
                            Object.entries(e.details).filter(([k]) => !['alarm_id', 'correlation_key'].includes(k)),
                          ),
                        )}
                      </pre>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function AlarmsHistoryPage() {
  const [stateFilter, setStateFilter] = useState<string>('cleared');
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const queryParams = useMemo(() => {
    const params: Record<string, string | number> = { limit: 200 };
    if (stateFilter) params.state = stateFilter;
    if (search) params.q = search;
    return params;
  }, [stateFilter, search]);

  const alarmsQuery = useQuery({
    queryKey: ['alarms-history', stateFilter, search],
    queryFn: () => fetchHistoryAlarms(queryParams),
  });

  const alarms = alarmsQuery.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        title="Alarm history"
        subtitle="Cleared, suppressed, and acknowledged alarms with full audit timeline"
        actions={
          <Link
            to="/alarms"
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to alarms
          </Link>
        }
      />

      <Card>
        <div className="flex flex-wrap gap-3 items-end mb-4">
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-500 mb-1">State</label>
            <Select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              options={[
                { value: '', label: 'All states' },
                { value: 'cleared', label: 'Cleared' },
                { value: 'suppressed', label: 'Suppressed' },
                { value: 'acknowledged', label: 'Acknowledged' },
                { value: 'active', label: 'Active' },
              ]}
            />
          </div>
          <div className="flex-[2] min-w-56">
            <Input
              label="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Message, source, event, category"
              className="py-1.5 text-xs"
            />
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setStateFilter('cleared');
              setSearch('');
            }}
          >
            Reset
          </Button>
        </div>

        {alarmsQuery.isLoading && (
          <p className="text-sm text-gray-400 text-center py-8">Loading history…</p>
        )}
        {alarmsQuery.isError && (
          <p className="text-sm text-red-500 text-center py-8">Failed to load history.</p>
        )}
        {!alarmsQuery.isLoading && !alarmsQuery.isError && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="w-8 px-3 py-2" />
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Severity</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">State</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Device</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Type</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Message</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">First seen</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Cleared at</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500">Actor</th>
                </tr>
              </thead>
              <tbody>
                {alarms.length === 0 && (
                  <tr>
                    <td colSpan={9} className="text-center text-gray-400 py-8 text-sm">No matching alarms.</td>
                  </tr>
                )}
                {alarms.map((alarm) => (
                  <HistoryRow
                    key={alarm.id}
                    alarm={alarm}
                    expanded={expandedId === alarm.id}
                    onToggle={() => setExpandedId(expandedId === alarm.id ? null : alarm.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
