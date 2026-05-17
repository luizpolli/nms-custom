import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { Badge, Button } from '../../../components/ui';
import { api } from '../../../lib/api';

interface Alarm {
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
}

interface AlarmDetailDrawerProps {
  alarm: Alarm;
  filtersKey: unknown[];
  onClose: () => void;
  onAck: (id: string) => void;
  onSuppress: (id: string) => void;
  onUnsuppress: (id: string) => void;
}

const SEVERITY_BADGE_MAP: Record<string, 'danger' | 'warning' | 'default' | 'success'> = {
  critical: 'danger',
  major: 'danger',
  minor: 'warning',
  warning: 'warning',
  info: 'default',
};

async function clearAlarm(id: string): Promise<void> {
  await api.post(`/alarms/${id}/clear`);
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="py-2 border-b border-gray-100 dark:border-gray-700 last:border-0">
      <dt className="text-xs text-gray-500 mb-0.5">{label}</dt>
      <dd className="text-sm text-gray-900 dark:text-gray-100">{children}</dd>
    </div>
  );
}

export function AlarmDetailDrawer({ alarm, filtersKey, onClose, onAck, onSuppress, onUnsuppress }: AlarmDetailDrawerProps) {
  const queryClient = useQueryClient();
  const clearMutation = useMutation({
    mutationFn: () => clearAlarm(alarm.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />
      <div className="relative ml-auto w-full max-w-md bg-white dark:bg-gray-900 shadow-xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h2 className="font-semibold text-gray-900 dark:text-white text-sm">Alarm details</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-1">
          <dl>
            <Field label="ID">{alarm.id}</Field>
            <Field label="Severity">
              <Badge variant={SEVERITY_BADGE_MAP[alarm.severity] ?? 'default'}>
                {alarm.severity}
              </Badge>
            </Field>
            <Field label="State">{alarm.state}</Field>
            <Field label="Device">{alarm.source_host}</Field>
            <Field label="Event type">{alarm.event_type}</Field>
            <Field label="Message">{alarm.message}</Field>
            <Field label="First seen">{new Date(alarm.first_seen).toLocaleString('en-US')}</Field>
            <Field label="Last seen">{new Date(alarm.last_seen).toLocaleString('en-US')}</Field>
            <Field label="Occurrences">{alarm.occurrence_count}</Field>
            {alarm.acknowledged_by && (
              <Field label="Acknowledged by">{alarm.acknowledged_by}</Field>
            )}
          </dl>

          {alarm.raw_varbinds && (
            <div className="mt-4">
              <p className="text-xs text-gray-500 mb-1">SNMP variables (raw_varbinds)</p>
              <pre className="text-xs bg-gray-50 dark:bg-gray-800 rounded p-3 overflow-x-auto whitespace-pre-wrap break-words">
                {JSON.stringify(alarm.raw_varbinds, null, 2)}
              </pre>
            </div>
          )}
        </div>

        <div className="flex gap-2 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
          {alarm.state !== 'acknowledged' && alarm.state !== 'suppressed' && (
            <Button size="sm" variant="outline" onClick={() => onAck(alarm.id)}>
              Acknowledge
            </Button>
          )}
          {alarm.state === 'suppressed' ? (
            <Button size="sm" variant="outline" onClick={() => onUnsuppress(alarm.id)}>
              Unsuppress
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => onSuppress(alarm.id)}>
              Suppress
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            onClick={() => clearMutation.mutate()}
            loading={clearMutation.isPending}
          >
            Clear
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose} className="ml-auto">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
