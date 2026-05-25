import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Plus, Trash2, Layers } from 'lucide-react';
import { api } from '../../lib/api';
import { PageHeader, Button, Input, Select, Modal, Spinner, EmptyState } from '../../components/ui';
import { CommandFormModal } from './CommandFormModal';
import { BulkRunModal } from './BulkRunModal';
import { RunHistoryPanel } from './RunHistoryPanel';
import { SchedulesPanel } from './SchedulesPanel';

interface Device {
  id: string;
  name: string;
  ip_address?: string;
}

interface Command {
  id: string;
  name: string;
  cli_command: string;
  output_path: string;
  device_id?: string;
}

interface RunResult {
  output: string;
  stdout?: string | null;
  stderr?: string | null;
}

type Tab = 'commands' | 'history' | 'schedules';

const TABS: { id: Tab; label: string }[] = [
  { id: 'commands', label: 'Commands' },
  { id: 'history', label: 'Run History' },
  { id: 'schedules', label: 'Schedules' },
];

export function CommandsPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const queryString = searchParams.toString();
  const [activeTab, setActiveTab] = useState<Tab>('commands');
  const [modalOpen, setModalOpen] = useState(false);
  const [editCommand, setEditCommand] = useState<Command | null>(null);
  const [outputModal, setOutputModal] = useState<{ title: string; output: string } | null>(null);
  const [bulkRunOpen, setBulkRunOpen] = useState(false);

  const [adHocDeviceId, setAdHocDeviceId] = useState('');
  const [adHocCli, setAdHocCli] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(queryString);
    const deviceId = params.get('device_id');
    const cli = params.get('command');
    const tab = params.get('tab') as Tab | null;
    if (tab && TABS.some((item) => item.id === tab)) {
      setActiveTab(tab);
    }
    if (deviceId || cli) {
      setActiveTab('commands');
      if (deviceId) setAdHocDeviceId(deviceId);
      if (cli) setAdHocCli(cli);
    }
  }, [queryString]);

  const { data: commandsData, isLoading, isError } = useQuery<Command[]>({
    queryKey: ['commands'],
    queryFn: () => api.get('/commands').then((r) => r.data),
  });

  const { data: devicesData } = useQuery<Device[] | { items: Device[] }>({
    queryKey: ['devices-select'],
    queryFn: () => api.get('/devices', { params: { limit: 200 } }).then((r) => r.data),
  });
  const devices: Device[] = Array.isArray(devicesData) ? devicesData : (devicesData?.items ?? []);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/commands/${id}`),
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: ['commands'] });
      const prev = queryClient.getQueryData<Command[]>(['commands']);
      queryClient.setQueryData<Command[]>(['commands'], (old) => old?.filter((c) => c.id !== id) ?? []);
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(['commands'], ctx?.prev);
      alert('Failed to delete command');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['commands'] }),
  });

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post<RunResult>(`/commands/${id}/run`).then((r) => r.data),
    onSuccess: (data, id) => {
      const cmd = commands.find((c) => c.id === id);
      setOutputModal({ title: cmd?.name ?? 'Output', output: data.output });
    },
    onError: (err) => {
      console.error('Run failed', err);
      alert('Failed to run command');
    },
  });

  const adHocMutation = useMutation({
    mutationFn: () =>
      api.post<RunResult>('/commands/run-ad-hoc', { device_id: adHocDeviceId, cli: adHocCli }).then((r) => r.data),
    onSuccess: (data) => {
      setOutputModal({ title: `Ad-hoc: ${adHocCli}`, output: data.output ?? data.stdout ?? data.stderr ?? '' });
    },
    onError: (err) => {
      console.error('Ad-hoc run failed', err);
      alert('Failed to run ad-hoc command');
    },
  });

  const commands = commandsData ?? [];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Commands"
        subtitle={`${commands.length} saved commands`}
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setBulkRunOpen(true)} disabled={commands.length === 0}>
              <Layers className="w-4 h-4 mr-1" /> Bulk Run
            </Button>
            <Button onClick={() => { setEditCommand(null); setModalOpen(true); }}>
              <Plus className="w-4 h-4 mr-1" /> Add Command
            </Button>
          </div>
        }
      />

      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex gap-4">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'commands' && (
        <div className="space-y-6">
          {isLoading && <Spinner />}
          {isError && <p className="text-red-500">Failed to load commands.</p>}
          {!isLoading && commands.length === 0 && (
            <EmptyState title="No commands" description="Create the first command using the button above." />
          )}

          {commands.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full text-sm divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800">
                  <tr>
                    {['Name', 'CLI command', 'Output path', 'Actions'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
                  {commands.map((cmd) => (
                    <tr key={cmd.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                      <td className="px-4 py-2 font-medium">{cmd.name}</td>
                      <td className="px-4 py-2 font-mono text-xs">{cmd.cli_command}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">{cmd.output_path || '—'}</td>
                      <td className="px-4 py-2">
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => runMutation.mutate(cmd.id)}
                            disabled={runMutation.isPending}
                            title="Run"
                          >
                            <Play className="w-4 h-4 text-green-600" />
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => { setEditCommand(cmd); setModalOpen(true); }}>
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              if (window.confirm(`Delete command "${cmd.name}"?`)) deleteMutation.mutate(cmd.id);
                            }}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50 dark:bg-gray-800 dark:border-gray-700">
            <div>
              <h3 className="font-semibold text-gray-700 dark:text-gray-300">Run ad-hoc command</h3>
              {searchParams.get('interface') && (
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Chassis context: {searchParams.get('interface')}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <Select
                label="Device"
                value={adHocDeviceId}
                onChange={(e) => setAdHocDeviceId(e.target.value)}
                options={[
                  { value: '', label: '— Select device —' },
                  ...devices.map((d) => ({ value: d.id, label: d.name })),
                ]}
                className="w-64"
              />
              <Input
                label="CLI command"
                value={adHocCli}
                onChange={(e) => setAdHocCli(e.target.value)}
                placeholder="show version"
                className="w-80"
              />
              <Button
                onClick={() => adHocMutation.mutate()}
                disabled={!adHocDeviceId || !adHocCli || adHocMutation.isPending}
              >
                <Play className="w-4 h-4 mr-1" />
                {adHocMutation.isPending ? 'Running...' : 'Run'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <RunHistoryPanel commands={commands} devices={devices} />
      )}

      {activeTab === 'schedules' && (
        <SchedulesPanel commands={commands} devices={devices} />
      )}

      {outputModal && (
        <Modal open={Boolean(outputModal)} onClose={() => setOutputModal(null)} title={outputModal.title}>
          <pre className="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-auto max-h-96 whitespace-pre-wrap font-mono">
            {outputModal.output || '(no output)'}
          </pre>
          <div className="flex justify-end mt-4">
            <Button variant="ghost" onClick={() => setOutputModal(null)}>Close</Button>
          </div>
        </Modal>
      )}

      <CommandFormModal open={modalOpen} onClose={() => setModalOpen(false)} command={editCommand} />
      <BulkRunModal open={bulkRunOpen} onClose={() => setBulkRunOpen(false)} commands={commands} />
    </div>
  );
}
