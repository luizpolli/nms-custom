import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Info } from 'lucide-react';
import { api } from '../../../lib/api';
import { Badge, Card, Spinner } from '../../../components/ui';
import type { ChassisTreeNode, ChassisViewModel } from './chassisTypes';
import { PortDetailPanel } from './PortDetailPanel';
import { ChassisCanvas } from './ChassisCanvas';
import { ComponentDetailsPanel } from './ComponentDetailsPanel';
import { DiscoveredElementsTree } from './DiscoveredElementsTree';
import { PortInventoryTable } from './PortInventoryTable';
import {
  buildPortInventoryRows,
  buildPortStatusByComponentId,
  collectManagedPorts,
  matchManagedInterface,
  type ManagedInterface,
  type PortStatus,
} from './portInventory';

interface ChassisViewProps {
  deviceName: string;
  deviceId?: string;
  dataUrl?: string;
  model?: ChassisViewModel;
}

async function fetchStaticChassisModel(dataUrl: string): Promise<ChassisViewModel> {
  const response = await fetch(dataUrl);
  if (!response.ok) {
    throw new Error(`Failed to load chassis model: ${response.status}`);
  }
  return response.json() as Promise<ChassisViewModel>;
}

async function fetchChassisModel(deviceId: string | undefined, dataUrl: string): Promise<ChassisViewModel> {
  if (deviceId) {
    const response = await api.get<ChassisViewModel>(`/devices/${deviceId}/chassis`);
    return response.data;
  }
  return fetchStaticChassisModel(dataUrl);
}

function firstSelectableNode(nodes: ChassisTreeNode[]): string | null {
  for (const node of nodes) {
    if (node.componentId) return node.componentId;
    const child = firstSelectableNode(node.children);
    if (child) return child;
  }
  return null;
}

export function ChassisView({ deviceName, deviceId, dataUrl = '/chassis-assets/asr903/normalized.json', model }: ChassisViewProps) {
  const query = useQuery({
    queryKey: ['chassis-view', deviceId ?? dataUrl],
    queryFn: () => fetchChassisModel(deviceId, dataUrl),
    enabled: !model,
  });
  const data = model ?? query.data;
  const isLoading = !model && query.isLoading;
  const isError = !model && query.isError;
  const managedInterfacesQuery = useQuery<ManagedInterface[]>({
    queryKey: ['chassis-managed-interfaces', deviceId],
    queryFn: () => api.get(`/devices/${deviceId}/managed-interfaces`).then((response) => response.data),
    enabled: Boolean(deviceId),
  });

  const defaultSelection = useMemo(() => (data ? firstSelectableNode(data.tree) : null), [data]);
  const managedInterfaces = useMemo(
    () => managedInterfacesQuery.data ?? [],
    [managedInterfacesQuery.data],
  );
  const portInventoryRows = useMemo(
    () => (data ? buildPortInventoryRows(data, managedInterfaces) : []),
    [data, managedInterfaces],
  );
  const portStatusByComponentId = useMemo(
    () => (data ? buildPortStatusByComponentId(data, managedInterfaces) : {}),
    [data, managedInterfaces],
  );
  const portStatusCounts = useMemo(() => {
    const counts: Record<PortStatus, number> = { up: 0, down: 0, 'admin-down': 0 };
    for (const info of Object.values(portStatusByComponentId)) {
      counts[info.status] += 1;
    }
    return counts;
  }, [portStatusByComponentId]);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [selectedPortId, setSelectedPortId] = useState<string | null>(null);
  const [portDetailPhysicalIndex, setPortDetailPhysicalIndex] = useState<number | null>(null);
  const [selectedViewId, setSelectedViewId] = useState<string>('front');
  const effectiveSelection = selectedComponentId ?? defaultSelection;

  if (isLoading) {
    return (
      <Card>
        <Spinner />
      </Card>
    );
  }

  if (isError || !data) {
    return (
      <Card>
        <p className="text-sm text-red-500">Failed to load chassis model.</p>
      </Card>
    );
  }

  const view = data.views.find((v) => v.id === selectedViewId) ?? data.views[0];
  const selectedComponent = effectiveSelection ? data.componentsById[effectiveSelection] : undefined;
  const selectedPorts = collectManagedPorts(selectedComponent, data.componentsById);
  const selectedPort = selectedPorts.find((port) => port.id === selectedPortId) ?? selectedPorts[0];
  const selectedInterface = matchManagedInterface(selectedPort, managedInterfaces);
  const physicalInventory = data.source?.physicalInventory;
  const inventorySourceLabel = physicalInventory?.matched
    ? `Entity-MIB ${physicalInventory.matched}/${physicalInventory.available}`
    : 'Static profile';
  const handleComponentSelect = (componentId: string) => {
    setSelectedComponentId(componentId);
    setSelectedPortId(null);
  };

  const handleHotspotDetail = (physicalIndex: number) => {
    setPortDetailPhysicalIndex(physicalIndex);
  };

  return (
    <>
    <Card className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-gray-300 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="flex flex-col gap-3 border-b border-gray-200 px-4 py-3 dark:border-gray-700 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <h2 className="truncate text-xl font-semibold text-gray-800 dark:text-gray-100">
              Chassis View-{deviceName}
            </h2>
            <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" />
            <Info className="h-5 w-5 shrink-0 text-gray-400" />
          </div>
          <div className="flex flex-wrap items-center gap-2 lg:justify-end lg:shrink-0">
            <Badge variant="success">Inventory mapped</Badge>
            <Badge variant={physicalInventory?.matched ? 'success' : 'default'}>{inventorySourceLabel}</Badge>
            <Badge variant="default">{data.platform}</Badge>
          </div>
        </div>

        <div className="relative min-h-[560px] bg-[#e7f1fb] dark:bg-gray-950">
          {/*
            Chassis-first responsive layout (no fancy grid placement):
            - Chassis always renders first in DOM and on its own row, full-width.
              This guarantees the chassis image gets the entire content width
              minus padding, regardless of viewport.
            - The tree + details panel sit below the chassis on a 2-col grid
              that activates from `md` (>=768px).  Below md they stack.

            This avoids the previous breakage where the chassis got squished
            into a narrow middle column at ~1200px laptop viewports.
          */}
          <div className="flex flex-col gap-5 p-4">
            {/* Row 1: chassis image, centered. Width is capped by aspect ratio:
               we compute a max-width so the chassis is never taller than
               ~360px regardless of its native aspect ratio. Tall chassis like
               NCS560 (aspect ~2.5:1) and flat ones like ASR920 (aspect ~10:1)
               both end up at a comfortable visual size on a laptop viewport. */}
            <div className="flex min-h-[260px] min-w-0 items-center justify-center px-2 sm:px-4 xl:px-6">
              {/* Size by aspect ratio so the chassis fits in a comfortable
                 visual box. Wide chassis (ASR920, NCS540, NCS55A1, ~10:1) get
                 the full 1280px cap. Tall chassis (NCS5508, ASR9010) get a
                 floor of 380px width so they don't shrink to a thin sliver. */}
              {(() => {
                const aspectRatio = view.width / view.height;
                const widthFromHeightCap = 360 * aspectRatio;
                const computedWidth = `min(1280px, max(380px, ${widthFromHeightCap}px))`;
                return (
                  <div className="w-full max-w-[1280px]" style={{ maxWidth: computedWidth }}>
                <div className="mb-3 flex items-center justify-between text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                  <div className="flex items-center gap-3">
                    <span>{view.label}</span>
                    {data.views.length > 1 && (
                      <div className="flex items-center gap-1 rounded-md border border-gray-300 bg-white p-0.5 shadow-sm dark:border-gray-600 dark:bg-gray-800">
                        {data.views.map((v) => (
                          <button
                            key={v.id}
                            type="button"
                            onClick={() => setSelectedViewId(v.id)}
                            className={`rounded px-2 py-0.5 text-[10px] font-semibold transition ${
                              v.id === view.id
                                ? 'bg-cisco-blue text-white shadow'
                                : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-700 dark:hover:text-gray-200'
                            }`}
                          >
                            {v.label ?? v.id.charAt(0).toUpperCase() + v.id.slice(1)}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <span>{view.hotspots.filter((hotspot) => hotspot.inventoryId).length}/{view.hotspots.length} mapped hotspots</span>
                </div>
                    <ChassisCanvas
                      model={data}
                      selectedComponentId={effectiveSelection}
                      onSelect={handleComponentSelect}
                      onHotspotDetail={deviceId ? handleHotspotDetail : undefined}
                      viewId={view.id}
                      portStatusByComponentId={portStatusByComponentId}
                    />
                  </div>
                );
              })()}
            </div>

            {/* Row 2: tree + details panel side-by-side from md (>=768px), stacked below. */}
            <div className="grid gap-5 md:grid-cols-[minmax(240px,300px)_minmax(0,1fr)]">
              <DiscoveredElementsTree
                tree={data.tree}
                componentsById={data.componentsById}
                managedInterfaces={managedInterfaces}
                selectedComponentId={effectiveSelection}
                onSelect={handleComponentSelect}
              />
              <ComponentDetailsPanel
                component={selectedComponent}
                componentsById={data.componentsById}
                managedPorts={selectedPorts}
                selectedPort={selectedPort}
                managedInterface={selectedInterface}
                hasLiveInterfaceLookup={Boolean(deviceId)}
                isLoadingInterfaces={managedInterfacesQuery.isLoading || managedInterfacesQuery.isFetching}
                deviceId={deviceId}
                onSelectPort={setSelectedPortId}
              />
            </div>

            <PortInventoryTable rows={portInventoryRows} hasLiveInterfaceLookup={Boolean(deviceId)} />
          </div>

          <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 rounded-full bg-white/90 px-3 py-2 text-xs text-gray-600 shadow dark:bg-gray-900/90 dark:text-gray-300">
            {Object.keys(portStatusByComponentId).length > 0 ? (
              <>
                <LegendDot className="bg-green-500" label={`Up (${portStatusCounts.up})`} />
                <LegendDot className="bg-red-500" label={`Down (${portStatusCounts.down})`} />
                <LegendDot className="bg-gray-400" label={`Admin down (${portStatusCounts['admin-down']})`} />
                <LegendDot className="bg-cisco-blue" label="Selected" />
              </>
            ) : (
              <>
                <LegendDot className="bg-green-500" label="Operational" />
                <LegendDot className="bg-cisco-blue" label="Selected" />
                <LegendDot className="bg-gray-400" label="Empty bay" />
              </>
            )}
          </div>
        </div>
      </div>
    </Card>

    {deviceId && portDetailPhysicalIndex != null && (
      <PortDetailPanel
        deviceId={deviceId}
        physicalIndex={portDetailPhysicalIndex}
        onClose={() => setPortDetailPhysicalIndex(null)}
      />
    )}
  </>);
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-full ${className}`} />
      {label}
    </span>
  );
}
