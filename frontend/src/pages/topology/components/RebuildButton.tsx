import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

interface Props {
  deviceId?: string;
  onSuccess?: () => void;
  onError?: (msg: string) => void;
}

export function RebuildButton({ deviceId, onSuccess, onError }: Props) {
  const qc = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      deviceId
        ? axios.post(`/api/topology/devices/${deviceId}/rebuild`)
        : axios.post('/api/topology/rebuild'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['topology'] });
      onSuccess?.();
    },
    onError: (err: Error) => {
      onError?.(err.message ?? 'Error al reconstruir topología');
    },
  });

  return (
    <button
      onClick={() => mutate()}
      disabled={isPending}
      className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60 transition-colors"
    >
      {isPending ? 'Reconstruyendo...' : deviceId ? 'Reconstruir dispositivo' : 'Reconstruir todo'}
    </button>
  );
}
