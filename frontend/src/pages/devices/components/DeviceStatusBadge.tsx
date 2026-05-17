import { Badge } from '../../../components/ui';

type DeviceStatus = 'reachable' | 'unreachable' | 'unknown' | 'polling';

interface DeviceStatusBadgeProps {
  status: string;
}

const statusVariantMap: Record<DeviceStatus, 'success' | 'danger' | 'warning' | 'default'> = {
  reachable: 'success',
  unreachable: 'danger',
  unknown: 'warning',
  polling: 'default',
};

const statusLabelMap: Record<DeviceStatus, string> = {
  reachable: 'Reachable',
  unreachable: 'Unreachable',
  unknown: 'Unknown',
  polling: 'Polling',
};

export function DeviceStatusBadge({ status }: DeviceStatusBadgeProps) {
  const key = status as DeviceStatus;
  const variant = statusVariantMap[key] ?? 'default';
  const label = statusLabelMap[key] ?? status;
  return <Badge variant={variant}>{label}</Badge>;
}
