import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Modal, Button, Input } from '../../components/ui';

interface Command {
  id: string;
  name: string;
  cli_command: string;
  output_path: string;
  device_id?: string;
}

interface CommandFormData {
  name: string;
  cli_command: string;
  output_path: string;
}

interface CommandFormModalProps {
  open: boolean;
  onClose: () => void;
  command?: Command | null;
}

const EMPTY_FORM: CommandFormData = { name: '', cli_command: '', output_path: '' };

export function CommandFormModal({ open, onClose, command }: CommandFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CommandFormData>(EMPTY_FORM);

  useEffect(() => {
    if (command) {
      setForm({
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
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
