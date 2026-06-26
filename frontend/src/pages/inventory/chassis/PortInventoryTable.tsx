import { Power, PowerOff } from 'lucide-react';
import { Badge, Button } from '../../../components/ui';
import { formatSpeedBps, type PortInventoryRow, type PortStatusInfo } from './portInventory';
import { PortStatusBadge } from './ComponentDetailsPanel';

/** Resolve the inventory componentId a port row maps to (for status + admin toggle). */
function rowComponentId(id: string): string | null {
  if (id.startsWith('component:')) return id.slice('component:'.length);
  if (id.startsWith('port:')) return id.split(':')[1] ?? null;
  return null;
}

export function PortInventoryTable({
  rows,
  hasLiveInterfaceLookup,
  statusByComponentId,
  onTogglePortAdmin,
  isDemo,
}: {
  rows: PortInventoryRow[];
  hasLiveInterfaceLookup: boolean;
  statusByComponentId: Record<string, PortStatusInfo>;
  onTogglePortAdmin: (componentId: string, portName?: string) => void;
  isDemo: boolean;
}) {
  const physicalCount = rows.filter((row) => row.kind === 'physical').length;
  const logicalCount = rows.filter((row) => row.kind === 'logical').length;

  return (
    <div className="rounded-lg border border-gray-200 bg-white/90 shadow dark:border-gray-700 dark:bg-gray-900/95">
      <div className="flex flex-col gap-2 border-b border-gray-200 px-4 py-3 dark:border-gray-700 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Port inventory</p>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Physical and logical ports</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge variant="default">{physicalCount} physical</Badge>
          <Badge variant={logicalCount ? 'success' : 'default'}>{logicalCount} logical</Badge>
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
          {hasLiveInterfaceLookup ? 'No port inventory has been collected for this device.' : 'Live interface records are not available in static preview.'}
        </p>
      ) : (
        <div className="max-h-72 overflow-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
            <thead className="sticky top-0 bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-900 dark:text-gray-400">
              <tr>
                <th className="px-4 py-2 text-left font-semibold">Type</th>
                <th className="px-4 py-2 text-left font-semibold">Name</th>
                <th className="px-4 py-2 text-left font-semibold">Source / Parent</th>
                <th className="px-4 py-2 text-left font-semibold">Index</th>
                <th className="px-4 py-2 text-left font-semibold">State</th>
                <th className="px-4 py-2 text-left font-semibold">Speed</th>
                <th className="px-4 py-2 text-left font-semibold">Admin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white dark:divide-gray-800 dark:bg-gray-900">
              {rows.map((row) => {
                const cid = rowComponentId(row.id);
                const status = cid ? statusByComponentId[cid]?.status : undefined;
                const willShut = status !== 'admin-down';
                return (
                <tr key={row.id} className="text-gray-700 dark:text-gray-300">
                  <td className="px-4 py-2">
                    <Badge variant={row.kind === 'physical' ? 'default' : 'success'}>
                      {row.kind === 'physical' ? 'Physical' : 'Logical'}
                    </Badge>
                  </td>
                  <td className="max-w-[220px] truncate px-4 py-2 font-medium text-gray-900 dark:text-gray-100">{row.name}</td>
                  <td className="max-w-[260px] truncate px-4 py-2 text-gray-500 dark:text-gray-400">
                    {row.componentName ?? row.source}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500 dark:text-gray-400">
                    {row.kind === 'physical' ? row.physicalIndex ?? '-' : row.ifIndex ?? '-'}
                  </td>
                  <td className="px-4 py-2">
                    {status ? (
                      <PortStatusBadge status={status} />
                    ) : (
                      <span className="text-gray-500 dark:text-gray-400">
                        {row.adminStatus || row.operStatus ? `${row.adminStatus ?? '-'}/${row.operStatus ?? '-'}` : '-'}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-500 dark:text-gray-400">{formatSpeedBps(row.speedBps)}</td>
                  <td className="px-4 py-2">
                    {cid && status ? (
                      <Button
                        type="button"
                        variant={willShut ? 'danger' : 'success'}
                        size="sm"
                        onClick={() => onTogglePortAdmin(cid, row.name)}
                        leftIcon={willShut ? <PowerOff className="h-3.5 w-3.5" /> : <Power className="h-3.5 w-3.5" />}
                        title={isDemo ? (willShut ? 'Apagar (simulado)' : 'Encender (simulado)') : willShut ? 'shutdown' : 'no shutdown'}
                      >
                        {willShut ? 'Shut' : 'No shut'}
                      </Button>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
