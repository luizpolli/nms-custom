import { useMutation } from '@tanstack/react-query';
import { RefreshCw } from 'lucide-react';
import { api } from '../../../lib/api';
import { Button } from '../../../components/ui';

interface PollButtonProps {
  deviceId: string;
  onSuccess?: () => void;
}

export function PollButton({ deviceId, onSuccess }: PollButtonProps) {
  const mutation = useMutation({
    mutationFn: () => api.post(`/devices/${deviceId}/poll`),
    onSuccess: () => {
      onSuccess?.();
    },
    onError: (err) => {
      console.error('Poll failed', err);
      alert('Error al consultar el dispositivo');
    },
  });

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      title="Consultar ahora"
    >
      <RefreshCw className={`w-4 h-4 ${mutation.isPending ? 'animate-spin' : ''}`} />
    </Button>
  );
}
