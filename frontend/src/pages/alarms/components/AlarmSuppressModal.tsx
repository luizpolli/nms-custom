import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal, Button, Input } from '../../../components/ui';
import { api } from '../../../lib/api';

interface AlarmSuppressModalProps {
  alarmId: string;
  onClose: () => void;
  filtersKey: unknown[];
}

async function suppressAlarm(id: string, byUser: string, reason: string): Promise<void> {
  await api.post(`/alarms/${id}/suppress`, { by_user: byUser, reason });
}

export function AlarmSuppressModal({ alarmId, onClose, filtersKey }: AlarmSuppressModalProps) {
  const [byUser, setByUser] = useState('');
  const [reason, setReason] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => suppressAlarm(alarmId, byUser, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
      queryClient.invalidateQueries({ queryKey: ['alarms-summary'] });
      queryClient.invalidateQueries({ queryKey: ['assurance-summary'] });
      onClose();
    },
  });

  return (
    <Modal open title="Suppress alarm" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Suppress alarm <span className="font-mono font-medium">{alarmId}</span>. It will stay visible with state <b>suppressed</b> and an audit entry.
        </p>
        <div>
          <label className="mb-1 block text-xs text-gray-500">User</label>
          <Input value={byUser} onChange={(e) => setByUser(e.target.value)} placeholder="user@domain" autoFocus />
        </div>
        <div>
          <label className="mb-1 block text-xs text-gray-500">Reason</label>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Maintenance window / known issue" />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={!byUser.trim() || mutation.isPending} loading={mutation.isPending}>
            Suppress
          </Button>
        </div>
        {mutation.isError && <p className="text-xs text-red-500">Failed to suppress alarm. Please try again.</p>}
      </div>
    </Modal>
  );
}
