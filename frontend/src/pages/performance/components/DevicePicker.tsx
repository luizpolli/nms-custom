import { useQuery } from '@tanstack/react-query';
import { Select } from '../../../components/ui';
import { api } from '../../../lib/api';

interface Device {
  id: string;
  name: string;
  hostname?: string;
}

interface DevicePickerProps {
  value: string;
  onChange: (deviceId: string) => void;
}

async function fetchDevices(): Promise<Device[]> {
  const { data } = await api.get<Device[]>('/devices');
  return data;
}

export function DevicePicker({ value, onChange }: DevicePickerProps) {
  const { data: devices = [], isLoading } = useQuery({
    queryKey: ['devices'],
    queryFn: fetchDevices,
    staleTime: 60_000,
  });

  const options = [
    { value: '', label: 'Seleccionar dispositivo…' },
    ...devices.map((d) => ({ value: d.id, label: d.name ?? d.hostname ?? d.id })),
  ];

  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
      options={options}
      aria-label="Seleccionar dispositivo"
    />
  );
}
