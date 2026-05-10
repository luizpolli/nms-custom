import { useState } from 'react';
import clsx from 'clsx';
import { ArrowUpDown } from 'lucide-react';
import { Badge, Button } from '../../../components/ui';

export interface Alarm {
  id: string;
  severity: string;
  state: string;
  source_host: string;
  event_type: string;
  message: string;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  raw_varbinds?: Record<string, unknown>;
  acknowledged_by?: string;
  _flash?: boolean;
}

interface AlarmTableProps {
  alarms: Alarm[];
  onView: (alarm: Alarm) => void;
  onAck: (id: string) => void;
  onClear: (id: string) => void;
}

type SortKey = keyof Pick<Alarm, 'severity' | 'state' | 'source_host' | 'first_seen' | 'last_seen' | 'occurrence_count'>;

const SEVERITY_BADGE_MAP: Record<string, 'danger' | 'warning' | 'default' | 'success'> = {
  critical: 'danger',
  major: 'danger',
  minor: 'warning',
  warning: 'warning',
  info: 'default',
};

const SEVERITY_ORDER: Record<string, number> = { critical: 0, major: 1, minor: 2, warning: 3, info: 4 };

function fmt(ts: string) {
  return new Date(ts).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

export function AlarmTable({ alarms, onView, onAck, onClear }: AlarmTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('last_seen');
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(false); }
  }

  const sorted = [...alarms].sort((a, b) => {
    let cmp = 0;
    if (sortKey === 'severity') cmp = (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
    else if (sortKey === 'occurrence_count') cmp = a.occurrence_count - b.occurrence_count;
    else cmp = String(a[sortKey]).localeCompare(String(b[sortKey]));
    return sortAsc ? cmp : -cmp;
  });

  function SortTh({ label, col }: { label: string; col: SortKey }) {
    return (
      <th
        className="px-3 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 cursor-pointer select-none whitespace-nowrap"
        onClick={() => toggleSort(col)}
      >
        <span className="inline-flex items-center gap-1">
          {label}
          <ArrowUpDown size={11} className={clsx(sortKey === col ? 'text-blue-500' : 'opacity-40')} />
        </span>
      </th>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 dark:bg-gray-800">
          <tr>
            <SortTh label="Severidad" col="severity" />
            <SortTh label="Estado" col="state" />
            <SortTh label="Dispositivo" col="source_host" />
            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-400">Tipo</th>
            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-400">Mensaje</th>
            <SortTh label="Primera vez" col="first_seen" />
            <SortTh label="Última vez" col="last_seen" />
            <SortTh label="Conteo" col="occurrence_count" />
            <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 dark:text-gray-400">Acciones</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
          {sorted.length === 0 && (
            <tr>
              <td colSpan={9} className="text-center text-gray-400 py-8 text-sm">Sin alarmas.</td>
            </tr>
          )}
          {sorted.map((alarm) => (
            <tr
              key={alarm.id}
              className={clsx(
                'hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors',
                alarm._flash && 'animate-pulse bg-yellow-50 dark:bg-yellow-900/20',
              )}
            >
              <td className="px-3 py-2 whitespace-nowrap">
                <Badge variant={SEVERITY_BADGE_MAP[alarm.severity] ?? 'default'}>
                  {alarm.severity}
                </Badge>
              </td>
              <td className="px-3 py-2 whitespace-nowrap text-gray-700 dark:text-gray-300">{alarm.state}</td>
              <td className="px-3 py-2 whitespace-nowrap font-mono text-xs text-gray-700 dark:text-gray-300">{alarm.source_host}</td>
              <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-600 dark:text-gray-400">{alarm.event_type}</td>
              <td className="px-3 py-2 max-w-xs truncate text-gray-700 dark:text-gray-300" title={alarm.message}>{alarm.message}</td>
              <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-500">{fmt(alarm.first_seen)}</td>
              <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-500">{fmt(alarm.last_seen)}</td>
              <td className="px-3 py-2 text-center text-xs font-mono">{alarm.occurrence_count}</td>
              <td className="px-3 py-2 whitespace-nowrap">
                <div className="flex gap-1">
                  <Button size="xs" variant="ghost" onClick={() => onView(alarm)}>Ver</Button>
                  {alarm.state !== 'acknowledged' && (
                    <Button size="xs" variant="outline" onClick={() => onAck(alarm.id)}>Reconocer</Button>
                  )}
                  <Button size="xs" variant="danger" onClick={() => onClear(alarm.id)}>Limpiar</Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
