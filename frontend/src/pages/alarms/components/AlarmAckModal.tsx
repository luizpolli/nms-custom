import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Modal, Button, Input } from '../../../components/ui';
import { api } from '../../../lib/api';

interface AlarmAckModalProps {
  alarmId: string;
  onClose: () => void;
  filtersKey: unknown[];
}

async function ackAlarm(id: string, byUser: string): Promise<void> {
  await api.post(`/alarms/${id}/ack`, { by_user: byUser });
}

export function AlarmAckModal({ alarmId, onClose, filtersKey }: AlarmAckModalProps) {
  const [byUser, setByUser] = useState('');
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => ackAlarm(alarmId, byUser),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarms', ...filtersKey] });
      onClose();
    },
  });

  return (
    <Modal title="Reconocer alarma" onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Ingresa tu usuario para reconocer la alarma <span className="font-mono font-medium">{alarmId}</span>.
        </p>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Usuario</label>
          <Input
            value={byUser}
            onChange={(e) => setByUser(e.target.value)}
            placeholder="usuario@dominio"
            autoFocus
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={!byUser.trim() || mutation.isPending}
            loading={mutation.isPending}
          >
            Reconocer
          </Button>
        </div>
        {mutation.isError && (
          <p className="text-xs text-red-500">Error al reconocer la alarma. Intenta de nuevo.</p>
        )}
      </div>
    </Modal>
  );
}
