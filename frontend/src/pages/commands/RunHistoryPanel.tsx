import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { api } from '../../lib/api';
import { Badge, Button, Select, Spinner, EmptyState } from '../../components/ui';

interface CommandRun {
  id: string;
  command_id: string | null;
  device_id: string;
  started_at: string;
  finished_at: string | null;
  exit_status: number | null;
  stdout: string | null;
  stderr: string | null;
  triggered_by: string;
}

interface Command {
  id: string;
  name: string;
}

interface Device {
  id: string;
  name: string;
}

interface RunHistoryPanelProps {
  commands: Command[];
  devices: Device[];
}

type ExportFormat = 'txt' | 'json' | 'csv';
type DeliveryMode = 'download' | 'email' | 'file';

export function RunHistoryPanel({ commands, devices }: RunHistoryPanelProps) {
  const [filterCommandId, setFilterCommandId] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [exportFormat, setExportFormat] = useState<ExportFormat>('txt');
  const [exportDelivery, setExportDelivery] = useState<DeliveryMode>('download');
  const [emailRecipients, setEmailRecipients] = useState('');

  const runsQuery = useQuery<CommandRun[]>({
    queryKey: ['command-runs', filterCommandId],
    queryFn: () =>
      filterCommandId
        ? api.get(`/commands/${filterCommandId}/runs`).then((r) => r.data)
        : Promise.resolve([]),
    enabled: Boolean(filterCommandId),
  });

  const exportMutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = { format: exportFormat, delivery: exportDelivery };
      if (exportDelivery === 'email') {
        body.recipients = emailRecipients.split(',').map((s) => s.trim()).filter(Boolean);
      }
      return api.post(`/commands/${filterCommandId}/runs/export`, body, {
        responseType: exportDelivery === 'download' ? 'blob' : 'json',
      }).then((r) => ({ data: r.data, headers: r.headers }));
    },
    onSuccess: ({ data, headers }) => {
      if (exportDelivery !== 'download') return;
      const disposition = (headers as Record<string, string>)['content-disposition'] ?? '';
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match?.[1] ?? `export.${exportFormat}`;
      const url = URL.createObjectURL(new Blob([data as BlobPart]));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    },
    onError: () => alert('Export failed'),
  });

  const commandOptions = [
    { value: '', label: '— Select command to load history —' },
    ...commands.map((c) => ({ value: c.id, label: c.name })),
  ];

  const formatOptions: { value: ExportFormat; label: string }[] = [
    { value: 'txt', label: 'TXT' },
    { value: 'json', label: 'JSON' },
    { value: 'csv', label: 'CSV' },
  ];

  const deliveryOptions: { value: DeliveryMode; label: string }[] = [
    { value: 'download', label: 'Download' },
    { value: 'email', label: 'Email' },
    { value: 'file', label: 'Save to server' },
  ];

  const runs = runsQuery.data ?? [];

  const deviceName = (id: string) => devices.find((d) => d.id === id)?.name ?? id.slice(0, 8);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-end">
        <Select
          label="Command"
          value={filterCommandId}
          onChange={(e) => setFilterCommandId(e.target.value)}
          options={commandOptions}
          className="w-64"
        />
        {filterCommandId && (
          <>
            <Select
              label="Format"
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value as ExportFormat)}
              options={formatOptions}
              className="w-28"
            />
            <Select
              label="Delivery"
              value={exportDelivery}
              onChange={(e) => setExportDelivery(e.target.value as DeliveryMode)}
              options={deliveryOptions}
              className="w-40"
            />
            {exportDelivery === 'email' && (
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-gray-700 dark:text-gray-300">Recipients (comma-sep)</label>
                <input
                  className="rounded border border-gray-300 px-2 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                  value={emailRecipients}
                  onChange={(e) => setEmailRecipients(e.target.value)}
                  placeholder="a@b.com, c@d.com"
                />
              </div>
            )}
            <Button
              size="sm"
              variant="secondary"
              onClick={() => exportMutation.mutate()}
              loading={exportMutation.isPending}
              disabled={runs.length === 0}
            >
              <Download className="w-4 h-4 mr-1" />
              Export
            </Button>
          </>
        )}
      </div>

      {!filterCommandId && (
        <EmptyState title="Select a command" description="Choose a command above to view its run history." />
      )}
      {filterCommandId && runsQuery.isLoading && <Spinner />}
      {filterCommandId && !runsQuery.isLoading && runs.length === 0 && (
        <EmptyState title="No history" description="This command has not been run yet." />
      )}

      {runs.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full text-sm divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Device', 'Started', 'Duration', 'Exit', 'Triggered by', ''].map((h) => (
                  <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
              {runs.map((run) => {
                const duration =
                  run.finished_at
                    ? `${((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s`
                    : '—';
                return (
                  <>
                    <tr key={run.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-3 py-2 font-medium">{deviceName(run.device_id)}</td>
                      <td className="px-3 py-2 text-xs text-gray-500">{new Date(run.started_at).toLocaleString()}</td>
                      <td className="px-3 py-2 text-xs">{duration}</td>
                      <td className="px-3 py-2">
                        <Badge variant={run.exit_status === 0 ? 'success' : run.exit_status == null ? 'warning' : 'danger'}>
                          {run.exit_status ?? '?'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">{run.triggered_by}</td>
                      <td className="px-3 py-2">
                        <button
                          className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                          onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                        >
                          {expandedId === run.id ? 'hide' : 'output'}
                        </button>
                      </td>
                    </tr>
                    {expandedId === run.id && (
                      <tr key={`${run.id}-out`}>
                        <td colSpan={6} className="px-3 py-2 bg-gray-900">
                          <pre className="text-green-400 text-xs whitespace-pre-wrap font-mono max-h-64 overflow-auto">
                            {run.stdout || run.stderr || '(no output)'}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
