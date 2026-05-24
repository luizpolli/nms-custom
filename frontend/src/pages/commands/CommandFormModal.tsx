import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select } from '../../components/ui';

interface Command {
  id: string;
  name: string;
  cli_command: string;
  output_path: string;
  device_id?: string;
}

interface Device {
  id: string;
  name: string;
  ip_address?: string;
}

interface CommandFormData {
  device_id: string;
  name: string;
  cli_command: string;
  output_path: string;
}

interface CommandFormModalProps {
  open: boolean;
  onClose: () => void;
  command?: Command | null;
}

const EMPTY_FORM: CommandFormData = { device_id: '', name: '', cli_command: '', output_path: '' };

export function CommandFormModal({ open, onClose, command }: CommandFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CommandFormData>(EMPTY_FORM);

  const { data: devicesData, isLoading: devicesLoading } = useQuery<Device[] | { items: Device[] }>({
    queryKey: ['devices-select'],
    queryFn: () => api.get('/devices', { params: { limit: 200 } }).then((r) => r.data),
    enabled: open,
  });

  const devices: Device[] = Array.isArray(devicesData) ? devicesData : (devicesData?.items ?? []);
  const deviceOptions = [
    { value: '', label: devicesLoading ? 'Loading devices...' : 'Select device...' },
    ...devices.map((device) => ({
      value: device.id,
      label: device.ip_address ? `${device.name} (${device.ip_address})` : device.name,
    })),
  ];

  useEffect(() => {
    if (command) {
      setForm({
        device_id: command.device_id ?? '',
        name: command.name,
        cli_command: command.cli_command,
        output_path: command.output_path,
      });
    } else {
      setForm(EMPTY_FORM);
    }
  }, [command, open]);

  const mutation = useMutation({
    mutationFn: (data: CommandFormData) =>
      command ? api.patch(`/commands/${command.id}`, data) : api.post('/commands', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['commands'] });
      onClose();
    },
    onError: (err) => {
      console.error('Save command failed', err);
      alert('Failed to save command');
    },
  });

  const handleSet = <K extends keyof CommandFormData>(key: K, value: CommandFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title={command ? 'Edit command' : 'Create command'}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Select
          label="Device"
          value={form.device_id}
          onChange={(e) => handleSet('device_id', e.target.value)}
          options={deviceOptions}
          required
          disabled={devicesLoading}
        />
        <Input label="Name" value={form.name} onChange={(e) => handleSet('name', e.target.value)} required />
        <Input
          label="CLI command"
          value={form.cli_command}
          onChange={(e) => handleSet('cli_command', e.target.value)}
          placeholder="show version"
          required
        />
        <Input
          label="Output path (output_path)"
          value={form.output_path}
          onChange={(e) => handleSet('output_path', e.target.value)}
          placeholder="/var/log/commands/"
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending || devicesLoading || !form.device_id}>
            {mutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
