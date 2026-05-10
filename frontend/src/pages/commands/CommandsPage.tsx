import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Play, Plus, Trash2 } from 'lucide-react';
import { api } from '../../lib/api';
import { PageHeader, Button, Input, Select, Modal, Spinner, EmptyState } from '../../components/ui';
import { CommandFormModal } from './CommandFormModal';

interface Device {
  id: string;
  name: string;
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
}

export function CommandsPage() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editCommand, setEditCommand] = useState<Command | null>(null);
  const [outputModal, setOutputModal] = useState<{ title: string; output: string } | null>(null);

  // Ad-hoc panel state
  const [adHocDeviceId, setAdHocDeviceId] = useState('');
  const [adHocCli, setAdHocCli] = useState('');

  const { data: commandsData, isLoading, isError } = useQuery<Command[]>({
    queryKey: ['commands'],
    queryFn: () => api.get('/commands').then((r) => r.data),
  });

  const { data: devicesData } = useQuery<{ items: Device[] }>({
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
      alert('Error al eliminar el comando');
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['commands'] }),
  });

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post<RunResult>(`/commands/${id}/run`).then((r) => r.data),
    onSuccess: (data, id) => {
      const cmd = commands.find((c) => c.id === id);
      setOutputModal({ title: cmd?.name ?? 'Salida', output: data.output });
    },
    onError: (err) => {
      console.error('Run failed', err);
      alert('Error al ejecutar el comando');
    },
  });

  const adHocMutation = useMutation({
    mutationFn: () =>
      api.post<RunResult>('/commands/run-ad-hoc', { device_id: adHocDeviceId, cli: adHocCli }).then((r) => r.data),
    onSuccess: (data) => {
      setOutputModal({ title: `Ad-hoc: ${adHocCli}`, output: data.output });
    },
    onError: (err) => {
      console.error('Ad-hoc run failed', err);
      alert('Error al ejecutar el comando ad-hoc');
    },
  });

  const commands = commandsData ?? [];

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="Comandos"
        subtitle={`${commands.length} comandos guardados`}
        actions={
          <Button onClick={() => { setEditCommand(null); setModalOpen(true); }}>
            <Plus className="w-4 h-4 mr-1" /> Crear comando
          </Button>
        }
      />

      {isLoading && <Spinner />}
      {isError && <p className="text-red-500">Error al cargar comandos.</p>}
      {!isLoading && commands.length === 0 && (
        <EmptyState title="Sin comandos" description="Crea el primer comando con el botón superior." />
      )}

      {commands.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {['Nombre', 'Comando CLI', 'Ruta de salida', 'Acciones'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {commands.map((cmd) => (
                <tr key={cmd.id} className="hover:bg-gray-50">
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
                        title="Ejecutar"
                      >
                        <Play className="w-4 h-4 text-green-600" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => { setEditCommand(cmd); setModalOpen(true); }}>
                        Editar
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (window.confirm(`¿Eliminar comando "${cmd.name}"?`)) deleteMutation.mutate(cmd.id);
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

      {/* Ad-hoc panel */}
      <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700">Ejecutar comando ad-hoc</h3>
        <div className="flex flex-wrap gap-3 items-end">
          <Select
            label="Dispositivo"
            value={adHocDeviceId}
            onChange={(e) => setAdHocDeviceId(e.target.value)}
            options={[
              { value: '', label: '— Selecciona dispositivo —' },
              ...devices.map((d) => ({ value: d.id, label: d.name })),
            ]}
            className="w-64"
          />
          <Input
            label="Comando CLI"
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
            {adHocMutation.isPending ? 'Ejecutando...' : 'Ejecutar'}
          </Button>
        </div>
      </div>

      {/* Output modal */}
      {outputModal && (
        <Modal open={Boolean(outputModal)} onClose={() => setOutputModal(null)} title={outputModal.title}>
          <pre className="bg-gray-900 text-green-400 p-4 rounded text-xs overflow-auto max-h-96 whitespace-pre-wrap font-mono">
            {outputModal.output || '(sin salida)'}
          </pre>
          <div className="flex justify-end mt-4">
            <Button variant="ghost" onClick={() => setOutputModal(null)}>Cerrar</Button>
          </div>
        </Modal>
      )}

      <CommandFormModal open={modalOpen} onClose={() => setModalOpen(false)} command={editCommand} />
    </div>
  );
}
