import { Handle, Position } from 'reactflow';

export interface DeviceNodeData {
  label: string;
  role?: string;
  vendor?: string;
  model?: string;
  status?: string;
}

// Map model string → topology icon path (served from public/topology-icons/)
function deviceIconSrc(model?: string, role?: string): string {
  const m = (model ?? '').toUpperCase();
  if (m.includes('NCS-55') || m.includes('NCS55'))   return '/topology-icons/card_ncs5500.svg';
  if (m.includes('NCS-56') || m.includes('NCS56'))   return '/topology-icons/card_ncs560.svg';
  if (m.includes('NCS-54') || m.includes('NCS54'))   return '/topology-icons/card_ncs540.svg';
  if (m.includes('NCS-50') || m.includes('NCS500'))  return '/topology-icons/card_ncs500.svg';
  if (m.includes('ASR-9')  || m.includes('ASR9'))    return '/topology-icons/card_asr9000.svg';
  if (m.includes('NCS-10') || m.includes('NCS1000')) return '/topology-icons/card_ncs1000.svg';
  if (role === 'access')                              return '/topology-icons/card_ncs500.svg';
  return '/topology-icons/card_generic.svg';
}

// Status → overlay icon (shown top-right of the card)
function statusIconSrc(status?: string): string | null {
  const map: Record<string, string> = {
    unreachable: '/topology-icons/unreachable.svg',
    degraded:    '/topology-icons/degraded.svg',
    critical:    '/topology-icons/critical.svg',
    major:       '/topology-icons/major.svg',
    minor:       '/topology-icons/minor.svg',
    warning:     '/topology-icons/warning.svg',
    reachable:   '/topology-icons/reachable.svg',
    cleared:     '/topology-icons/cleared.svg',
  };
  return status ? (map[status] ?? null) : null;
}

// Role → short label color
const ROLE_BADGE: Record<string, string> = {
  core:        'bg-blue-600 text-white',
  aggregation: 'bg-indigo-500 text-white',
  pe:          'bg-violet-500 text-white',
  access:      'bg-teal-500 text-white',
  'mobile-gw': 'bg-orange-500 text-white',
};

export function DeviceNode({ data }: { data: DeviceNodeData }) {
  const iconSrc    = deviceIconSrc(data.model, data.role);
  const statusSrc  = statusIconSrc(data.status);
  const badgeCls   = ROLE_BADGE[data.role ?? ''] ?? 'bg-gray-500 text-white';
  const isUnreach  = data.status === 'unreachable';

  return (
    <div
      className={`
        relative flex items-center gap-2 rounded-lg border bg-white dark:bg-gray-800
        px-2 py-1.5 shadow-md min-w-[170px] max-w-[200px]
        ${isUnreach ? 'border-red-400 opacity-70' : 'border-gray-300 dark:border-gray-600'}
      `}
    >
      <Handle type="target" position={Position.Left}  className="!bg-gray-400 !w-2 !h-2" />

      {/* Device icon */}
      <img
        src={iconSrc}
        alt={data.model ?? 'device'}
        className="h-8 w-8 flex-shrink-0 object-contain"
        draggable={false}
      />

      {/* Label + role */}
      <div className="flex min-w-0 flex-col">
        <span className="truncate text-[11px] font-semibold text-gray-800 dark:text-gray-100">
          {data.label}
        </span>
        {data.role && (
          <span className={`mt-0.5 inline-block self-start rounded px-1 py-px text-[9px] font-medium uppercase tracking-wide ${badgeCls}`}>
            {data.role}
          </span>
        )}
      </div>

      {/* Status overlay — top-right corner */}
      {statusSrc && (
        <img
          src={statusSrc}
          alt={data.status}
          className="absolute -right-2 -top-2 h-5 w-5 object-contain"
          draggable={false}
        />
      )}

      <Handle type="source" position={Position.Right} className="!bg-gray-400 !w-2 !h-2" />
    </div>
  );
}
