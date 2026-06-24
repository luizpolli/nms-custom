import { useQuery } from '@tanstack/react-query';
import { Select } from '../../../components/ui';
import { api } from '../../../lib/api';

interface InstancePickerProps {
  deviceId: string;
  kpiType: string;
  value: string;
  onChange: (objectId: string) => void;
}

async function fetchSeries(deviceId: string, kpiType: string): Promise<string[]> {
  const { data } = await api.get<string[]>(`/performance/devices/${deviceId}/kpis/series`, {
    params: { kpi_type: kpiType },
  });
  return data;
}

/** Picks one reported instance (e.g. a StarOS servname/vpnname context) for
 * a device+metric — without this, a chart blends every instance under that
 * device into one averaged line. */
export function InstancePicker({ deviceId, kpiType, value, onChange }: InstancePickerProps) {
  const { data: instances = [], isLoading } = useQuery({
    queryKey: ['kpi-series', deviceId, kpiType],
    queryFn: () => fetchSeries(deviceId, kpiType),
    enabled: Boolean(deviceId && kpiType),
    staleTime: 30_000,
  });

  if (!isLoading && instances.length <= 1) {
    return null;
  }

  const options = [
    { value: '', label: 'All instances (blended)' },
    ...instances.map((id) => ({ value: id, label: id })),
  ];

  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={isLoading}
      options={options}
      aria-label="Select instance"
    />
  );
}
