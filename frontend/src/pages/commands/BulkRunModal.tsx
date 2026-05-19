import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Play } from 'lucide-react';
import { api } from '../../lib/api';
import { Modal, Button, Select, Badge, Spinner } from '../../components/ui';

interface Device {
  id: string;
  name: string;
  ip_address?: string;
}

interface Command {
  id: string;
  name: string;
  cli_command: string;
}

interface BulkRunResult {
  device_id: string;
  exit_status: number | null;
  stdout: string | null;
  stderr: string | null;
  error: string | null;
}

interface BulkRunModalProps {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

export function BulkRunModal({ open, onClose, commands }: BulkRunModalProps) {
  const [selectedCommandId, setSelectedCommandId] = useState('');
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [results, setResults] = useState<BulkRunResult[] | null>(null);

  const { data: devicesData, isLoading: devicesLoading } = useQuery<Device[]>({
    queryKey: ['devices-bulk'],
    queryFn: () => api.get('/devices', { params: { limit: 500 } }).then((r) => {
      const d = r.data;
      return Array.isArray(d) ? d : (d?.items ?? []);
    }),
    enabled: open,
  });
  const devices: Device[] = devicesData ?? [];

  const bulkMutation = useMutation({
    mutationFn: () =>
      api.post<BulkRunResult[]>(`/commands/${selectedCommandId}/run-bulk`, {
        device_ids: selectedDeviceIds,
      }).then((r) => r.data),
    onSuccess: (data) => setResults(data),
    onError: () => alert('Bulk run failed'),
  });

  const toggleDevice = (id: string) => {
    setSelectedDeviceIds((prev) =>
      prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id],
    );
  };

  const handleClose = () => {
    setSelectedCommandId('');
    setSelectedDeviceIds([]);
    setResults(null);
    onClose();
  };

  const commandOptions = [
    { value: '', label: '— Select command —' },
    ...commands.map((c) => ({ value: c.id, label: `${c.name} (${c.cli_command})` })),
  ];

  return (
    <Modal open={open} onClose={handleClose} title="Bulk Run" size="lg">
      <div className="space-y-4">
        <Select
          label="Command"
          value={selectedCommandId}
          onChange={(e) => setSelectedCommandId(e.target.value)}
          options={commandOptions}
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
            Devices ({selectedDeviceIds.length} selected)
          </label>
          {devicesLoading ? (
            <Spinner />
          ) : (
            <div className="max-h-48 overflow-y-auto rounded border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-800">
              {devices.map((d) => (
                <label
                  key={d.id}
                  className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <input
                    type="checkbox"
                    checked={selectedDeviceIds.includes(d.id)}
                    onChange={() => toggleDevice(d.id)}
                  />
                  <span className="font-medium text-gray-900 dark:text-white">{d.name}</span>
                  {d.ip_address && <span className="text-gray-400 text-xs">{d.ip_address}</span>}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={handleClose}>Cancel</Button>
          <Button
            onClick={() => bulkMutation.mutate()}
            disabled={!selectedCommandId || selectedDeviceIds.length === 0}
            loading={bulkMutation.isPending}
          >
            <Play className="w-4 h-4 mr-1" />
            Run on {selectedDeviceIds.length} device{selectedDeviceIds.length !== 1 ? 's' : ''}
          </Button>
        </div>

        {results && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">Results</h4>
            <div className="overflow-x-auto rounded border border-gray-200 dark:border-gray-700">
              <table className="min-w-full text-xs divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {['Device', 'Exit', 'Output', 'Error'].map((h) => (
                      <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
                  {results.map((r) => {
                    const dev = devices.find((d) => d.id === r.device_id);
                    return (
                      <tr key={r.device_id}>
                        <td className="px-3 py-2 font-medium">{dev?.name ?? r.device_id}</td>
                        <td className="px-3 py-2">
                          <Badge variant={r.exit_status === 0 ? 'success' : r.error ? 'danger' : 'warning'}>
                            {r.error ? 'err' : String(r.exit_status ?? '?')}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 max-w-xs truncate font-mono">{r.stdout ?? '—'}</td>
                        <td className="px-3 py-2 text-red-500 max-w-xs truncate">{r.error ?? r.stderr ?? '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
