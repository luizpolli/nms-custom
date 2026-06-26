import { Activity, Bell, Power, PowerOff, TerminalSquare } from 'lucide-react';
import { Badge, Button, Card } from '../../../components/ui';
import type { ChassisComponent } from './chassisTypes';
import { formatSpeedBps, type ManagedInterface, type ManagedPort, type PortStatus, type PortStatusInfo } from './portInventory';

/** Shared status nomenclature (Up / Down / Admin down) with colour. */
export const PORT_STATUS_META: Record<PortStatus, { label: string; dot: string; badge: string }> = {
  up: { label: 'Up', dot: 'bg-green-500', badge: 'bg-green-100 text-green-700 ring-green-300 dark:bg-green-900/40 dark:text-green-300 dark:ring-green-700/60' },
  down: { label: 'Down', dot: 'bg-red-500', badge: 'bg-red-100 text-red-700 ring-red-300 dark:bg-red-900/40 dark:text-red-300 dark:ring-red-700/60' },
  'admin-down': { label: 'Admin down', dot: 'bg-amber-500', badge: 'bg-amber-100 text-amber-700 ring-amber-300 dark:bg-amber-900/40 dark:text-amber-300 dark:ring-amber-700/60' },
};

export function PortStatusBadge({ status }: { status?: PortStatus | null }) {
  if (!status) return <span className="text-xs text-gray-400 dark:text-gray-500">—</span>;
  const meta = PORT_STATUS_META[status];
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${meta.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}

export function ComponentDetailsPanel({
  component,
  componentsById,
  managedPorts,
  selectedPort,
  managedInterface,
  hasLiveInterfaceLookup,
  isLoadingInterfaces,
  deviceId,
  onSelectPort,
  statusByComponentId,
  onTogglePortAdmin,
  isDemo,
}: {
  component?: ChassisComponent;
  componentsById: Record<string, ChassisComponent>;
  managedPorts: ManagedPort[];
  selectedPort?: ManagedPort;
  managedInterface?: ManagedInterface;
  hasLiveInterfaceLookup: boolean;
  isLoadingInterfaces: boolean;
  deviceId?: string;
  onSelectPort: (portId: string) => void;
  statusByComponentId: Record<string, PortStatusInfo>;
  onTogglePortAdmin: (componentId: string, portName?: string) => void;
  isDemo: boolean;
}) {
  return (
    <Card className="space-y-4 border-gray-300 bg-white/90 dark:border-gray-700 dark:bg-gray-900/95">
      {!component ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">Select a discovered element.</p>
      ) : (
        <>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Selected component</p>
              <h3 className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-100">{component.displayName}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">{component.description ?? component.type}</p>
            </div>
            <Badge variant={component.operStatus === 'up' || component.operStatus === 'on' ? 'success' : 'default'}>
              {component.operStatus ?? 'unknown'}
            </Badge>
          </div>

          <div className="grid gap-3 text-sm">
            <MetricLine label="Type" value={component.type} />
            <MetricLine label="PID / Type ID" value={component.typeId ?? '-'} />
            <MetricLine label="Serial" value={component.serialNumber ?? '-'} />
            <MetricLine label="Physical index" value={String(component.physicalIndex ?? '-')} />
            <MetricLine label="Contained by" value={String(component.containedPhysicalIndex ?? '-')} />
            <MetricLine label="Service state" value={String(component.serviceState ?? '-')} />
            <MetricLine label="Inventory source" value={component.source?.type ?? 'static-profile'} />
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Managed ports</p>
              {managedPorts.length > 0 && <Badge variant="default">{managedPorts.length} mapped</Badge>}
            </div>
            {managedPorts.length === 0 ? (
              <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
                No ports mapped for this component or its child modules.
              </p>
            ) : (
              <PortInventoryPanel
                ports={managedPorts}
                selectedPort={selectedPort}
                managedInterface={managedInterface}
                hasLiveInterfaceLookup={hasLiveInterfaceLookup}
                isLoadingInterfaces={isLoadingInterfaces}
                deviceId={deviceId}
                componentsById={componentsById}
                onSelectPort={onSelectPort}
                statusByComponentId={statusByComponentId}
                onTogglePortAdmin={onTogglePortAdmin}
                isDemo={isDemo}
              />
            )}
          </div>
        </>
      )}
    </Card>
  );
}

function PortInventoryPanel({
  ports,
  selectedPort,
  managedInterface,
  hasLiveInterfaceLookup,
  isLoadingInterfaces,
  deviceId,
  componentsById,
  onSelectPort,
  statusByComponentId,
  onTogglePortAdmin,
  isDemo,
}: {
  ports: ManagedPort[];
  selectedPort?: ManagedPort;
  managedInterface?: ManagedInterface;
  hasLiveInterfaceLookup: boolean;
  isLoadingInterfaces: boolean;
  deviceId?: string;
  componentsById: Record<string, ChassisComponent>;
  onSelectPort: (portId: string) => void;
  statusByComponentId: Record<string, PortStatusInfo>;
  onTogglePortAdmin: (componentId: string, portName?: string) => void;
  isDemo: boolean;
}) {
  const selectedComponent = selectedPort ? componentsById[selectedPort.componentId] : undefined;
  const selectedStatus = selectedPort ? statusByComponentId[selectedPort.componentId]?.status : undefined;
  const willShut = selectedStatus !== 'admin-down';

  return (
    <div className="space-y-3">
      <div className="max-h-56 overflow-auto rounded-md border border-gray-200 dark:border-gray-700">
        {ports.map((port) => {
          const active = selectedPort?.id === port.id;
          return (
            <button
              key={`${port.componentId}-${port.id}`}
              type="button"
              onClick={() => onSelectPort(port.id)}
              className={`grid w-full grid-cols-[1fr_auto] gap-3 border-b border-gray-100 px-3 py-2 text-left text-sm last:border-b-0 dark:border-gray-800 ${
                active ? 'bg-cisco-blue text-white' : 'bg-white text-gray-800 hover:bg-gray-50 dark:bg-gray-900 dark:text-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              <span className="min-w-0">
                <span className="block truncate font-medium">{port.name ?? `Port ${port.id}`}</span>
                <span className={`block truncate text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                  {port.componentName}
                </span>
              </span>
              <span className="flex flex-col items-end gap-1">
                <PortStatusBadge status={statusByComponentId[port.componentId]?.status} />
                <span className={`font-mono text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                  {port.portId ?? port.id}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {selectedPort && (
        <div className="rounded-md border border-cisco-blue/30 bg-cisco-blue/5 p-3 text-sm dark:border-cisco-blue/50 dark:bg-cisco-blue/10">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate font-semibold text-gray-900 dark:text-gray-100">{selectedPort.name ?? `Port ${selectedPort.id}`}</p>
              <p className="truncate text-xs text-gray-500 dark:text-gray-400">{selectedPort.componentName}</p>
            </div>
            <PortStatusBadge status={selectedStatus} />
          </div>
          <div className="grid gap-2">
            <MetricLine label="Port ID" value={String(selectedPort.portId ?? selectedPort.id)} />
            <MetricLine label="Parent module" value={selectedPort.componentTypeId ?? selectedPort.componentName} />
            <MetricLine label="Physical index" value={String(selectedComponent?.physicalIndex ?? '-')} />
          </div>
          <div className="mt-3 border-t border-cisco-blue/20 pt-3 dark:border-cisco-blue/30">
            <Button
              type="button"
              variant={willShut ? 'danger' : 'success'}
              size="sm"
              className="w-full"
              onClick={() => onTogglePortAdmin(selectedPort.componentId, selectedPort.name)}
              leftIcon={willShut ? <PowerOff className="h-4 w-4" /> : <Power className="h-4 w-4" />}
            >
              {willShut ? 'Apagar puerto (shutdown)' : 'Encender puerto (no shutdown)'}
            </Button>
            <p className="mt-1.5 text-center text-[11px] text-gray-500 dark:text-gray-400">
              {isDemo
                ? 'Modo demo: cambia el estado de forma simulada.'
                : 'Genera el comando shut/no shut hacia la consola del equipo.'}
            </p>
          </div>
        </div>
      )}

      <InterfaceBindingPanel
        selectedPort={selectedPort}
        managedInterface={managedInterface}
        hasLiveInterfaceLookup={hasLiveInterfaceLookup}
        isLoadingInterfaces={isLoadingInterfaces}
        deviceId={deviceId}
      />
    </div>
  );
}

function InterfaceBindingPanel({
  selectedPort,
  managedInterface,
  hasLiveInterfaceLookup,
  isLoadingInterfaces,
  deviceId,
}: {
  selectedPort?: ManagedPort;
  managedInterface?: ManagedInterface;
  hasLiveInterfaceLookup: boolean;
  isLoadingInterfaces: boolean;
  deviceId?: string;
}) {
  if (!selectedPort) return null;

  const canManage = Boolean(deviceId && managedInterface);
  const targetInterface = managedInterface?.name ?? selectedPort.name ?? selectedPort.id;
  const commandQuery = new URLSearchParams({
    ...(deviceId ? { device_id: deviceId } : {}),
    interface: targetInterface,
    command: `show interface ${targetInterface}`,
  }).toString();

  return (
    <div className="rounded-md border border-gray-200 bg-white p-3 text-sm dark:border-gray-700 dark:bg-gray-900">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Live interface binding</p>
          <p className="mt-1 font-semibold text-gray-900 dark:text-gray-100">
            {isLoadingInterfaces
              ? 'Loading interface records...'
              : managedInterface
                ? managedInterface.name
                : hasLiveInterfaceLookup
                  ? 'No persisted interface match'
                  : 'Example port only'}
          </p>
        </div>
        <Badge variant={managedInterface ? 'success' : 'default'}>{managedInterface ? 'Bound' : 'Unbound'}</Badge>
      </div>

      {managedInterface ? (
        <div className="mb-3 grid gap-2">
          <MetricLine label="Admin / Oper" value={`${managedInterface.admin_status ?? '-'} / ${managedInterface.oper_status ?? '-'}`} />
          <MetricLine label="Speed" value={formatSpeedBps(managedInterface.speed_bps)} />
          <MetricLine label="MAC" value={managedInterface.mac_address ?? '-'} />
          <MetricLine label="Role" value={managedInterface.role ?? '-'} />
        </div>
      ) : (
        <p className="mb-3 text-xs text-gray-500 dark:text-gray-400">
          {hasLiveInterfaceLookup
            ? 'The chassis port is visible, but it does not match a persisted managed interface yet.'
            : 'Pass a live device ID into Chassis View to bind this port to managed interfaces, alarms, services, and commands.'}
        </p>
      )}

      <div className="grid grid-cols-1 gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canManage}
          onClick={() => { window.location.href = `/commands?${commandQuery}`; }}
          leftIcon={<TerminalSquare className="h-4 w-4" />}
        >
          Run show interface
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canManage}
          onClick={() => { window.location.href = `/monitoring-policies?device_id=${encodeURIComponent(deviceId ?? '')}&interface=${encodeURIComponent(targetInterface)}`; }}
          leftIcon={<Activity className="h-4 w-4" />}
        >
          Monitoring policy
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!canManage}
          onClick={() => { window.location.href = `/alarms?device_id=${encodeURIComponent(deviceId ?? '')}&object_type=interface&object_id=${encodeURIComponent(managedInterface?.id ?? '')}`; }}
          leftIcon={<Bell className="h-4 w-4" />}
        >
          Related alarms
        </Button>
      </div>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-2 last:border-0 dark:border-gray-800">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right font-medium text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}
