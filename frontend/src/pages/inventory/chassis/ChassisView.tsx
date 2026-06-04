import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, Bell, CheckCircle2, Info, Maximize2, Minus, Plus, TerminalSquare } from 'lucide-react';
import { api } from '../../../lib/api';
import { Badge, Button, Card, Spinner } from '../../../components/ui';
import type { ChassisComponent, ChassisComponentPort, ChassisHotspot, ChassisTreeNode, ChassisViewModel, ChassisViewImage, ComponentAlarmInfo } from './chassisTypes';
import { PortDetailPanel } from './PortDetailPanel';

interface ChassisViewProps {
  deviceName: string;
  deviceId?: string;
  dataUrl?: string;
  model?: ChassisViewModel;
}

type ManagedPort = ChassisComponentPort & {
  componentId: string;
  componentName: string;
  componentTypeId?: string;
};

type ManagedInterface = {
  id: string;
  if_index?: number | null;
  name: string;
  description?: string | null;
  alias?: string | null;
  mac_address?: string | null;
  admin_status?: string | null;
  oper_status?: string | null;
  speed_bps?: number | null;
  interface_type?: string | null;
  role?: string | null;
};

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

function collectManagedPorts(
  component: ChassisComponent | undefined,
  componentsById: Record<string, ChassisComponent>,
): ManagedPort[] {
  if (!component) return [];

  const ports: ManagedPort[] = component.ports.map((port) => ({
    ...port,
    componentId: component.id,
    componentName: component.displayName,
    componentTypeId: component.typeId,
  }));

  for (const childId of component.childIds) {
    ports.push(...collectManagedPorts(componentsById[childId], componentsById));
  }

  return ports.sort((a, b) => {
    const left = a.name ?? String(a.portId ?? a.id);
    const right = b.name ?? String(b.portId ?? b.id);
    return left.localeCompare(right, undefined, { numeric: true, sensitivity: 'base' });
  });
}

function normalizeInterfaceName(value?: string | number | null): string {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/^gigabitethernet/, 'gi')
    .replace(/^tengigabitethernet/, 'te')
    .replace(/^hundredgigabitethernet/, 'hu');
}

function matchManagedInterface(port: ManagedPort | undefined, interfaces: ManagedInterface[]): ManagedInterface | undefined {
  if (!port) return undefined;
  const portName = normalizeInterfaceName(port.name);
  const portId = String(port.portId ?? port.id);

  return interfaces.find((iface) => {
    const names = [iface.name, iface.description, iface.alias].map(normalizeInterfaceName);
    return names.includes(portName) || String(iface.if_index ?? '') === portId;
  });
}

function containsComponent(
  componentsById: Record<string, ChassisComponent>,
  ancestorId: string | null | undefined,
  candidateId: string | null | undefined,
): boolean {
  if (!ancestorId || !candidateId) return false;
  if (ancestorId === candidateId) return true;
  const ancestor = componentsById[ancestorId];
  if (!ancestor) return false;
  return ancestor.childIds.some((childId) => containsComponent(componentsById, childId, candidateId));
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
  const managedInterfaces = managedInterfacesQuery.data ?? [];
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
          </div>

          <div className="absolute bottom-4 left-4 flex flex-wrap gap-2 rounded-full bg-white/90 px-3 py-2 text-xs text-gray-600 shadow dark:bg-gray-900/90 dark:text-gray-300">
            <LegendDot className="bg-green-500" label="Operational" />
            <LegendDot className="bg-cisco-blue" label="Selected" />
            <LegendDot className="bg-gray-400" label="Empty bay" />
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

function DiscoveredElementsTree({
  tree,
  componentsById,
  selectedComponentId,
  onSelect,
}: {
  tree: ChassisTreeNode[];
  componentsById: Record<string, ChassisComponent>;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}) {
  return (
    <div className="max-h-[430px] overflow-auto rounded-lg border border-gray-200 bg-white/90 p-3 shadow dark:border-gray-700 dark:bg-gray-900/95">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Discovered elements</p>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Inventory tree</p>
        </div>
        <Badge variant="success">Synced</Badge>
      </div>
      <div className="space-y-1 text-sm">
        {tree.map((node) => (
          <TreeNodeRow
            key={node.id}
            node={node}
            depth={0}
            componentsById={componentsById}
            selectedComponentId={selectedComponentId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}

function TreeNodeRow({
  node,
  depth,
  componentsById,
  selectedComponentId,
  onSelect,
}: {
  node: ChassisTreeNode;
  depth: number;
  componentsById: Record<string, ChassisComponent>;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}) {
  const component = componentsById[node.componentId];
  const active = selectedComponentId === node.componentId;
  const portCount = collectManagedPorts(component, componentsById).length;

  return (
    <div>
      <button
        type="button"
        onClick={() => onSelect(node.componentId)}
        className={`grid w-full grid-cols-[1fr_auto] gap-2 rounded px-2 py-2 text-left transition ${
          active ? 'bg-cisco-blue text-white' : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        <span className="min-w-0">
          <span className="block truncate font-medium">{node.label}</span>
          <span className={`block truncate text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
            {component?.typeId ?? component?.type ?? node.type}
          </span>
        </span>
        <span className="flex flex-col items-end gap-1 text-xs">
          {component?.operStatus && <span>{component.operStatus}</span>}
          {portCount > 0 && <span className={active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}>{portCount} ports</span>}
        </span>
      </button>
      {node.children.map((child) => (
        <TreeNodeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          componentsById={componentsById}
          selectedComponentId={selectedComponentId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

const ZOOM_MIN = 1;
const ZOOM_MAX = 5;
const ZOOM_STEP = 0.25;

function clampZoom(value: number) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, value));
}

function clampPan(pan: { x: number; y: number }, zoom: number, frame: { width: number; height: number } | null) {
  if (!frame || zoom <= 1) return { x: 0, y: 0 };
  const maxX = (frame.width * (zoom - 1)) / 2;
  const maxY = (frame.height * (zoom - 1)) / 2;
  return {
    x: Math.min(maxX, Math.max(-maxX, pan.x)),
    y: Math.min(maxY, Math.max(-maxY, pan.y)),
  };
}

const ALARM_DOT_STYLES: Record<ComponentAlarmInfo['maxSeverity'], string> = {
  critical: 'bg-red-500 animate-pulse',
  major: 'bg-orange-500',
  minor: 'bg-yellow-400',
  warning: 'bg-blue-400',
  info: 'bg-gray-400',
};

function AlarmDot({ severity }: { severity: ComponentAlarmInfo['maxSeverity'] }) {
  return (
    <span
      aria-label={`${severity} alarm`}
      className={`pointer-events-none absolute right-0.5 top-0.5 h-2 w-2 rounded-full ring-1 ring-white/60 ${ALARM_DOT_STYLES[severity]}`}
    />
  );
}

const ALARM_LEGEND_ITEMS: { severity: ComponentAlarmInfo['maxSeverity']; label: string; color: string }[] = [
  { severity: 'critical', label: 'Critical', color: 'bg-red-500' },
  { severity: 'major',    label: 'Major',    color: 'bg-orange-500' },
  { severity: 'minor',    label: 'Minor',    color: 'bg-yellow-400' },
  { severity: 'warning',  label: 'Warning',  color: 'bg-blue-400' },
];

function ChassisCanvas({
  model,
  selectedComponentId,
  onSelect,
  onHotspotDetail,
  viewId,
}: {
  model: ChassisViewModel;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
  onHotspotDetail?: (physicalIndex: number) => void;
  viewId?: string;
}) {
  const view = (viewId ? model.views.find((v) => v.id === viewId) : undefined) ?? model.views[0];
  const frameRef = useRef<HTMLDivElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Reset zoom + pan when the device or the active view changes, so a
  // zoomed-in NCS560 doesn't carry its zoom state over to the next chassis.
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [model.deviceId, model.profileId, view.id]);
  const dragState = useRef<{ pointerId: number; startX: number; startY: number; originX: number; originY: number; moved: boolean } | null>(null);

  const frameSize = () => {
    const el = frameRef.current;
    return el ? { width: el.clientWidth, height: el.clientHeight } : null;
  };

  const applyZoom = (next: number) => {
    const clamped = clampZoom(next);
    setZoom(clamped);
    setPan((current) => clampPan(current, clamped, frameSize()));
  };

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && !event.metaKey && !event.altKey && Math.abs(event.deltaY) < 25) return;
    event.preventDefault();
    const delta = -event.deltaY * 0.0015;
    applyZoom(zoom + delta * (zoom + 1));
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (zoom <= 1 || event.button !== 0) return;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    dragState.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originX: pan.x,
      originY: pan.y,
      moved: false,
    };
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;
    if (!state.moved && Math.hypot(dx, dy) > 4) state.moved = true;
    setPan(clampPan({ x: state.originX + dx, y: state.originY + dy }, zoom, frameSize()));
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    const state = dragState.current;
    if (!state || state.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    dragState.current = null;
  };

  const consumedClick = (event: ReactPointerEvent<HTMLButtonElement>) => {
    return Boolean(dragState.current?.moved) || event.defaultPrevented;
  };

  return (
    <div className="relative rounded-md border border-gray-400 bg-gray-200 p-2 shadow-2xl dark:border-gray-700 dark:bg-gray-800">
      <div
        ref={frameRef}
        className="relative mx-auto w-full overflow-hidden touch-none"
        style={{ aspectRatio: `${view.width} / ${view.height}`, cursor: zoom > 1 ? (dragState.current ? 'grabbing' : 'grab') : 'default' }}
        onWheel={handleWheel}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      >
        <div
          className="absolute inset-0 origin-center"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transition: dragState.current ? 'none' : 'transform 120ms ease-out' }}
        >
          <img
            src={view.image}
            alt={`${model.platform} ${view.label}`}
            className="absolute inset-0 h-full w-full select-none"
            draggable={false}
          />
          {view.hotspots.map((hotspot) => (
            <SlotAsset key={`${hotspot.id}-asset`} hotspot={hotspot} view={view} />
          ))}
          {view.hotspots.map((hotspot) => {
            const selected = containsComponent(model.componentsById, hotspot.inventoryId, selectedComponentId);
            const canSelect = Boolean(hotspot.inventoryId);
            const alarmInfo: ComponentAlarmInfo | undefined =
              hotspot.inventoryId ? model.alarmsByComponentId?.[hotspot.inventoryId] : undefined;
            return (
              <button
                key={hotspot.id}
                type="button"
                disabled={!canSelect}
                title={hotspot.metadata?.sourceName ?? hotspot.label}
                aria-label={`Select ${hotspot.metadata?.sourceName ?? hotspot.label}`}
                onPointerUp={(event) => {
                  if (consumedClick(event)) event.preventDefault();
                }}
                onClick={(event) => {
                  if (dragState.current?.moved) {
                    event.preventDefault();
                    return;
                  }
                  if (hotspot.inventoryId) onSelect(hotspot.inventoryId);
                  if (onHotspotDetail && hotspot.physicalIndex != null) {
                    onHotspotDetail(Number(hotspot.physicalIndex));
                  }
                }}
                className={`absolute rounded-sm border-2 transition ${
                  selected
                    ? 'border-cisco-blue bg-cisco-blue/20 shadow-[0_0_0_4px_rgba(0,124,186,0.25)]'
                    : canSelect
                      ? 'border-transparent bg-green-500/0 hover:border-cisco-blue/70 hover:bg-cisco-blue/10'
                      : 'border-gray-400/40 bg-gray-500/10'
                }`}
                style={percentBounds(hotspot, view)}
              >
                {alarmInfo && <AlarmDot severity={alarmInfo.maxSeverity} />}
              </button>
            );
          })}
        </div>
      </div>
      {model.alarmSummary && model.alarmSummary.total > 0 && (
        <div className="absolute left-4 top-4 flex flex-col gap-1 rounded-md bg-white/95 px-2 py-1.5 shadow ring-1 ring-gray-300 dark:bg-gray-900/95 dark:ring-gray-700">
          <span className="mb-0.5 text-[9px] font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Alarms</span>
          {ALARM_LEGEND_ITEMS.filter(({ severity }) => (model.alarmSummary?.[severity] ?? 0) > 0).map(({ severity, label, color }) => (
            <div key={severity} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ring-1 ring-white/60 ${color}${severity === 'critical' ? ' animate-pulse' : ''}`} />
              <span className="text-[10px] text-gray-700 dark:text-gray-300">{label}</span>
              <span className="ml-auto text-[10px] font-mono font-semibold text-gray-800 dark:text-gray-200">{model.alarmSummary?.[severity]}</span>
            </div>
          ))}
        </div>
      )}
      <div className="absolute right-4 top-4 flex flex-col gap-1 rounded-md bg-white/95 p-1 shadow ring-1 ring-gray-300 dark:bg-gray-900/95 dark:ring-gray-700">
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() => applyZoom(zoom + ZOOM_STEP)}
          disabled={zoom >= ZOOM_MAX}
          className="rounded p-1 text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() => applyZoom(zoom - ZOOM_STEP)}
          disabled={zoom <= ZOOM_MIN}
          className="rounded p-1 text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          aria-label="Reset zoom"
          onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
          disabled={zoom === 1 && pan.x === 0 && pan.y === 0}
          className="rounded p-1 text-gray-700 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          <Maximize2 className="h-4 w-4" />
        </button>
        <span className="px-1 text-center text-[10px] font-mono text-gray-500 dark:text-gray-400">{Math.round(zoom * 100)}%</span>
      </div>
    </div>
  );
}

function SlotAsset({ hotspot, view }: { hotspot: ChassisHotspot; view: ChassisViewImage }) {
  if (!hotspot.asset) return null;

  return (
    <img
      src={hotspot.asset.image}
      alt=""
      aria-hidden="true"
      className={`pointer-events-none absolute object-fill ${hotspot.empty ? 'opacity-95' : ''}`}
      draggable={false}
      style={percentBounds(hotspot, view)}
    />
  );
}

function percentBounds(hotspot: ChassisHotspot, view: ChassisViewImage) {
  return {
    left: `${(hotspot.bounds.x / view.width) * 100}%`,
    top: `${(hotspot.bounds.y / view.height) * 100}%`,
    width: `${(hotspot.bounds.w / view.width) * 100}%`,
    height: `${(hotspot.bounds.h / view.height) * 100}%`,
  };
}

function ComponentDetailsPanel({
  component,
  componentsById,
  managedPorts,
  selectedPort,
  managedInterface,
  hasLiveInterfaceLookup,
  isLoadingInterfaces,
  deviceId,
  onSelectPort,
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
}: {
  ports: ManagedPort[];
  selectedPort?: ManagedPort;
  managedInterface?: ManagedInterface;
  hasLiveInterfaceLookup: boolean;
  isLoadingInterfaces: boolean;
  deviceId?: string;
  componentsById: Record<string, ChassisComponent>;
  onSelectPort: (portId: string) => void;
}) {
  const selectedComponent = selectedPort ? componentsById[selectedPort.componentId] : undefined;

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
              <span className={`font-mono text-xs ${active ? 'text-white/80' : 'text-gray-500 dark:text-gray-400'}`}>
                {port.portId ?? port.id}
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
            <Badge variant={selectedComponent?.operStatus === 'up' || selectedComponent?.operStatus === 'on' ? 'success' : 'default'}>
              {selectedComponent?.operStatus ?? 'known'}
            </Badge>
          </div>
          <div className="grid gap-2">
            <MetricLine label="Port ID" value={String(selectedPort.portId ?? selectedPort.id)} />
            <MetricLine label="Parent module" value={selectedPort.componentTypeId ?? selectedPort.componentName} />
            <MetricLine label="Physical index" value={String(selectedComponent?.physicalIndex ?? '-')} />
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

function formatSpeedBps(speed?: number | null) {
  if (!speed) return '-';
  if (speed >= 1_000_000_000) return `${(speed / 1_000_000_000).toFixed(1)} Gbps`;
  if (speed >= 1_000_000) return `${(speed / 1_000_000).toFixed(1)} Mbps`;
  if (speed >= 1_000) return `${(speed / 1_000).toFixed(1)} Kbps`;
  return `${speed} bps`;
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-2 last:border-0 dark:border-gray-800">
      <span className="text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right font-medium text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-2.5 w-2.5 rounded-full ${className}`} />
      {label}
    </span>
  );
}
