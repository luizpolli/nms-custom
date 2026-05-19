import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Play, Plus, Trash2 } from 'lucide-react';
import { api } from '../../lib/api';
import { Badge, Button, Input, Modal, Select, Spinner, EmptyState } from '../../components/ui';

interface CommandSchedule {
  id: string;
  name: string;
  command_id: string;
  device_ids: string[];
  tag: string | null;
  cron_expr: string | null;
  interval_seconds: number | null;
  enabled: boolean;
  last_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

interface Command {
  id: string;
  name: string;
}

interface Device {
  id: string;
  name: string;
}

interface SchedulesPanelProps {
  commands: Command[];
  devices: Device[];
}

interface ScheduleForm {
  name: string;
  command_id: string;
  device_ids: string[];
  tag: string;
  cron_expr: string;
  interval_seconds: string;
  enabled: boolean;
}

const EMPTY_FORM: ScheduleForm = {
  name: '',
  command_id: '',
  device_ids: [],
  tag: '',
  cron_expr: '',
  interval_seconds: '',
  enabled: true,
};

export function SchedulesPanel({ commands, devices }: SchedulesPanelProps) {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editSchedule, setEditSchedule] = useState<CommandSchedule | null>(null);
  const [form, setForm] = useState<ScheduleForm>(EMPTY_FORM);

  const schedulesQuery = useQuery<CommandSchedule[]>({
    queryKey: ['command-schedules'],
    queryFn: () => api.get('/command-schedules').then((r) => r.data),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['command-schedules'] });

  const saveMutation = useMutation({
    mutationFn: (data: ScheduleForm) => {
      const body = {
        name: data.name,
        command_id: data.command_id,
        device_ids: data.device_ids,
        tag: data.tag || null,
        cron_expr: data.cron_expr || null,
        interval_seconds: data.interval_seconds ? Number(data.interval_seconds) : null,
        enabled: data.enabled,
      };
      return editSchedule
        ? api.patch(`/command-schedules/${editSchedule.id}`, body)
        : api.post('/command-schedules', body);
    },
    onSuccess: () => {
      invalidate();
      setFormOpen(false);
      setEditSchedule(null);
      setForm(EMPTY_FORM);
    },
    onError: () => alert('Failed to save schedule'),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/command-schedules/${id}`),
    onSuccess: invalidate,
    onError: () => alert('Failed to delete schedule'),
  });

  const runNowMutation = useMutation({
    mutationFn: (id: string) => api.post(`/command-schedules/${id}/run-now`).then((r) => r.data),
    onSuccess: (_, id) => {
      invalidate();
      alert(`Schedule ${id} triggered successfully`);
    },
    onError: () => alert('Run-now failed'),
  });

  const openCreate = () => {
    setEditSchedule(null);
    setForm(EMPTY_FORM);
    setFormOpen(true);
  };

  const openEdit = (s: CommandSchedule) => {
    setEditSchedule(s);
    setForm({
      name: s.name,
      command_id: s.command_id,
      device_ids: s.device_ids,
      tag: s.tag ?? '',
      cron_expr: s.cron_expr ?? '',
      interval_seconds: s.interval_seconds != null ? String(s.interval_seconds) : '',
      enabled: s.enabled,
    });
    setFormOpen(true);
  };

  const toggleDevice = (id: string) => {
    setForm((prev) => ({
      ...prev,
      device_ids: prev.device_ids.includes(id)
        ? prev.device_ids.filter((d) => d !== id)
        : [...prev.device_ids, id],
    }));
  };

  const commandOptions = [
    { value: '', label: '— Select command —' },
    ...commands.map((c) => ({ value: c.id, label: c.name })),
  ];

  const commandName = (id: string) => commands.find((c) => c.id === id)?.name ?? id.slice(0, 8);

  const schedules = schedulesQuery.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={openCreate}>
          <Plus className="w-4 h-4 mr-1" /> New schedule
        </Button>
      </div>

      {schedulesQuery.isLoading && <Spinner />}
      {!schedulesQuery.isLoading && schedules.length === 0 && (
        <EmptyState title="No schedules" description="Create a schedule to run commands automatically." />
      )}

      {schedules.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
          <table className="min-w-full text-sm divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {['Name', 'Command', 'Schedule', 'Devices', 'Status', 'Last run', 'Actions'].map((h) => (
                  <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800 bg-white dark:bg-gray-900">
              {schedules.map((s) => (
                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  <td className="px-3 py-2 font-medium">{s.name}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">{commandName(s.command_id)}</td>
                  <td className="px-3 py-2 text-xs font-mono">
                    {s.cron_expr ?? (s.interval_seconds ? `every ${s.interval_seconds}s` : '—')}
                  </td>
                  <td className="px-3 py-2 text-xs">{s.device_ids.length}</td>
                  <td className="px-3 py-2">
                    <Badge variant={!s.enabled ? 'warning' : s.last_status === 'error' ? 'danger' : 'success'}>
                      {!s.enabled ? 'disabled' : (s.last_status ?? 'ok')}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-500">
                    {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Run now"
                        onClick={() => runNowMutation.mutate(s.id)}
                        disabled={runNowMutation.isPending}
                      >
                        <Play className="w-4 h-4 text-green-600" />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => openEdit(s)}>Edit</Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (window.confirm(`Delete schedule "${s.name}"?`)) deleteMutation.mutate(s.id);
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

      <Modal
        open={formOpen}
        onClose={() => { setFormOpen(false); setEditSchedule(null); setForm(EMPTY_FORM); }}
        title={editSchedule ? 'Edit schedule' : 'Create schedule'}
        size="lg"
      >
        <form
          className="space-y-4"
          onSubmit={(e) => { e.preventDefault(); saveMutation.mutate(form); }}
        >
          <Input
            label="Name"
            required
            value={form.name}
            onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
          />
          <Select
            label="Command"
            required
            options={commandOptions}
            value={form.command_id}
            onChange={(e) => setForm((p) => ({ ...p, command_id: e.target.value }))}
          />
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Cron expression"
              placeholder="0 * * * *"
              value={form.cron_expr}
              onChange={(e) => setForm((p) => ({ ...p, cron_expr: e.target.value }))}
            />
            <Input
              label="Interval (seconds, min 60)"
              type="number"
              min="60"
              placeholder="3600"
              value={form.interval_seconds}
              onChange={(e) => setForm((p) => ({ ...p, interval_seconds: e.target.value }))}
            />
          </div>
          <Input
            label="Tag filter (optional)"
            placeholder="core-routers"
            value={form.tag}
            onChange={(e) => setForm((p) => ({ ...p, tag: e.target.value }))}
          />
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Devices ({form.device_ids.length} selected)
            </label>
            <div className="max-h-40 overflow-y-auto rounded border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-800">
              {devices.map((d) => (
                <label
                  key={d.id}
                  className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  <input
                    type="checkbox"
                    checked={form.device_ids.includes(d.id)}
                    onChange={() => toggleDevice(d.id)}
                  />
                  <span className="text-gray-900 dark:text-white">{d.name}</span>
                </label>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.checked }))}
            />
            Enabled
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => { setFormOpen(false); setEditSchedule(null); setForm(EMPTY_FORM); }}>
              Cancel
            </Button>
            <Button type="submit" loading={saveMutation.isPending} disabled={!form.name || !form.command_id}>
              {editSchedule ? 'Update' : 'Create'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
