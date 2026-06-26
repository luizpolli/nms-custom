import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Info, Maximize2 } from 'lucide-react';
import { api } from '../../../lib/api';
import { Badge, Card, Spinner } from '../../../components/ui';
import type { ChassisComponent, ChassisHotspot, ChassisTreeNode, ChassisViewImage, ChassisViewModel } from './chassisTypes';
import { PortDetailPanel } from './PortDetailPanel';
import { ChassisCanvas } from './ChassisCanvas';
import { ComponentDetailsPanel, InterfaceBindingPanel } from './ComponentDetailsPanel';
import { DiscoveredElementsTree } from './DiscoveredElementsTree';
import { PortInventoryTable } from './PortInventoryTable';
import { CardZoomModal, type CardZoomData } from './CardZoomModal';
import {
  buildPortInventoryRows,
  buildPortStatusByComponentId,
  collectManagedPorts,
  matchManagedInterface,
  type ManagedInterface,
  type PortStatus,
  type PortStatusInfo,
} from './portInventory';

interface ChassisViewProps {
  deviceName: string;
  deviceId?: string;
  dataUrl?: string;
  model?: ChassisViewModel;
  /** Extra cards rendered in the left column, above the Discovered Elements tree
   *  (e.g. Software & lifecycle / Environment snapshot). */
  leftColumnExtras?: ReactNode;
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

const PORT_HOTSPOT_RE = /^(?:QSFP|SFP|Gi|GE|Te|Hu|Fo|Fa|Eth|Mgmt|\d+\/\d)/i;
const SLOT_HOTSPOT_RE = /^(?:RP\d|Line Card|Fan|Power Module)/i;

function generateDemoPortStatusByHotspot(model: ChassisViewModel): Record<string, PortStatusInfo> {
  const result: Record<string, PortStatusInfo> = {};
  let idx = 0;
  for (const view of model.views) {
    for (const hotspot of view.hotspots) {
      const label = hotspot.label ?? '';
      if (SLOT_HOTSPOT_RE.test(label) || !PORT_HOTSPOT_RE.test(label)) continue;
      const slot = idx % 10;
      idx++;
      if (slot >= 9) continue; // ~10% no-SFP / empty → gray in legend
      result[hotspot.id] = { status: slot >= 7 ? 'down' : 'up', interfaceName: label };
    }
  }
  return result;
}

function isDescendantComponent(
  componentsById: Record<string, ChassisComponent>,
  ancestorId: string | null | undefined,
  candidateId: string | null | undefined,
): boolean {
  if (!ancestorId || !candidateId) return false;
  if (ancestorId === candidateId) return true;
  const ancestor = componentsById[ancestorId];
  if (!ancestor) return false;
  return ancestor.childIds.some((childId) => isDescendantComponent(componentsById, childId, candidateId));
}

function boundsInside(
  inner: ChassisHotspot['bounds'],
  outer: ChassisHotspot['bounds'],
): boolean {
  return (
    inner.x >= outer.x - 1 &&
    inner.x + inner.w <= outer.x + outer.w + 1 &&
    inner.y >= outer.y - 1 &&
    inner.y + inner.h <= outer.y + outer.h + 1
  );
}

/**
 * Resolve the line-card faceplate + its mapped ports for the current selection
 * (the card module itself, or any of its ports). Returns null when the
 * selection isn't a port-bearing card, so the zoom affordance only appears for
 * cards EPNM would let you drill into.
 */
function buildZoomCard(
  view: ChassisViewImage,
  selection: string | null,
  componentsById: Record<string, ChassisComponent>,
  statusByComponentId: Record<string, PortStatusInfo>,
  statusByHotspotId: Record<string, PortStatusInfo>,
): CardZoomData | null {
  if (!selection) return null;
  for (const slot of view.hotspots) {
    if (!slot.asset?.image) continue;
    const portHotspots = view.hotspots.filter(
      (hotspot) =>
        hotspot !== slot &&
        PORT_HOTSPOT_RE.test(hotspot.label ?? '') &&
        boundsInside(hotspot.bounds, slot.bounds),
    );
    if (portHotspots.length === 0) continue;
    const ownsSelection =
      slot.inventoryId === selection ||
      isDescendantComponent(componentsById, slot.inventoryId, selection) ||
      portHotspots.some((hotspot) => hotspot.inventoryId === selection);
    if (!ownsSelection) continue;

    const ports = portHotspots
      .map((hotspot) => ({
        id: hotspot.id,
        label: hotspot.label ?? hotspot.id,
        status:
          (hotspot.inventoryId ? statusByComponentId[hotspot.inventoryId] : undefined)?.status ??
          statusByHotspotId[hotspot.id]?.status,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true, sensitivity: 'base' }));

    const component = slot.inventoryId ? componentsById[slot.inventoryId] : undefined;
    return {
      typeId: slot.asset.typeId ?? slot.metadata?.sourceTypeId ?? slot.label ?? 'Card',
      name: slot.metadata?.sourceName ?? component?.displayName ?? slot.label ?? 'Card',
      description: component?.description,
      image: slot.asset.image,
      // A taller-than-wide slot means the card seats vertically (ASR9010);
      // a wider slot is a horizontal chassis (ASR9006).
      vertical: slot.bounds.h > slot.bounds.w,
      ports,
    };
  }
  return null;
}

export function ChassisView({ deviceName, deviceId, dataUrl = '/chassis-assets/asr903/normalized.json', model, leftColumnExtras }: ChassisViewProps) {
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
  // Demo / static mode: generate synthetic port colours when no live interface data is available
  const portStatusByHotspotId = useMemo(() => {
    if (deviceId || !data || Object.keys(portStatusByComponentId).length > 0) return {};
    return generateDemoPortStatusByHotspot(data);
  }, [deviceId, data, portStatusByComponentId]);
  // Admin shut/no-shut overrides (demo: simulated; live: routed to /commands).
  const [adminOverrides, setAdminOverrides] = useState<Record<string, PortStatus>>({});
  // Unified componentId -> status: base poll/static, folding synthetic hotspot
  // colours into componentId space, then applying admin overrides on top. Drives
  // the chassis icons, both panels and the legend so a toggle updates everything.
  const effectivePortStatusByComponentId = useMemo(() => {
    const merged: Record<string, PortStatusInfo> = { ...portStatusByComponentId };
    if (data) {
      for (const v of data.views) {
        for (const h of v.hotspots) {
          if (h.inventoryId && !merged[h.inventoryId] && portStatusByHotspotId[h.id]) {
            merged[h.inventoryId] = portStatusByHotspotId[h.id];
          }
        }
      }
      for (const [cid, status] of Object.entries(adminOverrides)) {
        const prev = merged[cid];
        merged[cid] = {
          status,
          interfaceName: prev?.interfaceName ?? data.componentsById[cid]?.displayName ?? cid,
          adminStatus: status === 'admin-down' ? 'down' : 'up',
          operStatus: status === 'up' ? 'up' : 'down',
        };
      }
    }
    return merged;
  }, [portStatusByComponentId, portStatusByHotspotId, adminOverrides, data]);
  const portStatusCounts = useMemo(() => {
    const counts: Record<PortStatus, number> = { up: 0, down: 0, 'admin-down': 0 };
    for (const info of Object.values(effectivePortStatusByComponentId)) {
      counts[info.status] += 1;
    }
    return counts;
  }, [effectivePortStatusByComponentId]);
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(null);
  const [selectedPortId, setSelectedPortId] = useState<string | null>(null);
  const [portDetailPhysicalIndex, setPortDetailPhysicalIndex] = useState<number | null>(null);
  const [selectedViewId, setSelectedViewId] = useState<string>('front');
  const [zoomOpen, setZoomOpen] = useState(false);
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
  const zoomCard = buildZoomCard(
    view,
    effectiveSelection,
    data.componentsById,
    portStatusByComponentId,
    portStatusByHotspotId,
  );
  const handleComponentSelect = (componentId: string) => {
    setSelectedComponentId(componentId);
    setSelectedPortId(null);
    setZoomOpen(false);
  };

  const isDemo = !deviceId;
  const handleTogglePortAdmin = (componentId: string, portName?: string) => {
    const current = effectivePortStatusByComponentId[componentId]?.status;
    const next: PortStatus = current === 'admin-down' ? 'up' : 'admin-down';
    if (isDemo) {
      // Demo / static profile: simulate the admin flip so the chassis icon,
      // panels and legend update live.
      setAdminOverrides((prev) => ({ ...prev, [componentId]: next }));
      return;
    }
    // Live device: hand the shut / no-shut command off to the console page.
    const iface = portName ?? data.componentsById[componentId]?.displayName ?? '';
    const command = `interface ${iface}\n ${next === 'admin-down' ? 'shutdown' : 'no shutdown'}`;
    const query = new URLSearchParams({ device_id: deviceId ?? '', interface: iface, command }).toString();
    window.location.href = `/commands?${query}`;
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
            {zoomCard && zoomCard.ports.length > 0 && (
              <button
                type="button"
                onClick={() => setZoomOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-md border border-cisco-blue/40 bg-cisco-blue/10 px-2.5 py-1 text-xs font-semibold text-cisco-blue transition hover:bg-cisco-blue/20"
              >
                <Maximize2 className="h-3.5 w-3.5" />
                View card ({zoomCard.typeId})
              </button>
            )}
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
                      portStatusByComponentId={effectivePortStatusByComponentId}
                      portStatusByHotspotId={portStatusByHotspotId}
                    />
                  </div>
                );
              })()}
            </div>

            {/* Row 2: left column (extras + tree) and the details panel on the right. */}
            <div className="grid gap-5 lg:grid-cols-[minmax(320px,420px)_minmax(0,1fr)]">
              <div className="space-y-5">
                {leftColumnExtras}
                <DiscoveredElementsTree
                  tree={data.tree}
                  componentsById={data.componentsById}
                  managedInterfaces={managedInterfaces}
                  selectedComponentId={effectiveSelection}
                  onSelect={handleComponentSelect}
                />
              </div>
              <div className="space-y-5">
                <ComponentDetailsPanel
                  component={selectedComponent}
                  componentsById={data.componentsById}
                  managedPorts={selectedPorts}
                  selectedPort={selectedPort}
                  onSelectPort={setSelectedPortId}
                  statusByComponentId={effectivePortStatusByComponentId}
                />
                <PortInventoryTable
                  rows={portInventoryRows}
                  hasLiveInterfaceLookup={Boolean(deviceId)}
                  statusByComponentId={effectivePortStatusByComponentId}
                  onTogglePortAdmin={handleTogglePortAdmin}
                  isDemo={isDemo}
                />
                <InterfaceBindingPanel
                  selectedPort={selectedPort}
                  managedInterface={selectedInterface}
                  hasLiveInterfaceLookup={Boolean(deviceId)}
                  isLoadingInterfaces={managedInterfacesQuery.isLoading || managedInterfacesQuery.isFetching}
                  deviceId={deviceId}
                />
              </div>
            </div>
          </div>

          <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 rounded-full bg-white/90 px-3 py-2 text-xs text-gray-600 shadow dark:bg-gray-900/90 dark:text-gray-300">
            {Object.keys(effectivePortStatusByComponentId).length > 0 ? (
              <>
                <LegendDot icon="/chassis-icons/up.svg" label={`Up (${portStatusCounts.up})`} />
                <LegendDot icon="/chassis-icons/down.svg" label={`Down (${portStatusCounts.down})`} />
                <LegendDot icon="/chassis-icons/fi-admindown.svg" label={`Admin down (${portStatusCounts['admin-down']})`} />
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

    {zoomOpen && zoomCard && (
      <CardZoomModal card={zoomCard} onClose={() => setZoomOpen(false)} />
    )}
  </>);
}

function LegendDot({ className, icon, label }: { className?: string; icon?: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      {icon
        ? <img src={icon} alt="" className="h-3.5 w-3.5 shrink-0 object-contain" draggable={false} />
        : <span className={`h-2.5 w-2.5 rounded-full ${className ?? ''}`} />
      }
      {label}
    </span>
  );
}
