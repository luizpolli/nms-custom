import { useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react';
import { Maximize2, Minus, Plus } from 'lucide-react';
import type { ChassisComponent, ChassisHotspot, ChassisViewModel, ChassisViewImage, ComponentAlarmInfo } from './chassisTypes';
import type { PortStatus, PortStatusInfo } from './portInventory';
import { shouldRenderOverlay } from './overlayPolicy';

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

const PORT_STATUS_DOT_STYLES: Record<PortStatus, string> = {
  up: 'bg-green-500',
  down: 'bg-red-500',
  'admin-down': 'bg-gray-400',
};

const PORT_STATUS_LABELS: Record<PortStatus, string> = {
  up: 'up',
  down: 'down',
  'admin-down': 'admin down',
};

function PortStatusDot({ status }: { status: PortStatus }) {
  return (
    <span
      aria-label={`port ${PORT_STATUS_LABELS[status]}`}
      className={`pointer-events-none absolute bottom-0.5 left-0.5 h-2 w-2 rounded-full ring-1 ring-white/60 ${PORT_STATUS_DOT_STYLES[status]}`}
    />
  );
}

const ALARM_LEGEND_ITEMS: { severity: ComponentAlarmInfo['maxSeverity']; label: string; color: string }[] = [
  { severity: 'critical', label: 'Critical', color: 'bg-red-500' },
  { severity: 'major',    label: 'Major',    color: 'bg-orange-500' },
  { severity: 'minor',    label: 'Minor',    color: 'bg-yellow-400' },
  { severity: 'warning',  label: 'Warning',  color: 'bg-blue-400' },
];

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

export function ChassisCanvas({
  model,
  selectedComponentId,
  onSelect,
  onHotspotDetail,
  viewId,
  portStatusByComponentId,
}: {
  model: ChassisViewModel;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
  onHotspotDetail?: (physicalIndex: number) => void;
  viewId?: string;
  portStatusByComponentId?: Record<string, PortStatusInfo>;
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
          {view.hotspots.map((hotspot) =>
            shouldRenderOverlay(model.profileId, hotspot.id) ? (
              <SlotAsset key={`${hotspot.id}-asset`} hotspot={hotspot} view={view} />
            ) : null
          )}
          {view.hotspots.map((hotspot) => {
            const selected = containsComponent(model.componentsById, hotspot.inventoryId, selectedComponentId);
            const canSelect = Boolean(hotspot.inventoryId);
            const showHotspotChrome = shouldRenderOverlay(model.profileId, hotspot.id);
            const alarmInfo: ComponentAlarmInfo | undefined =
              hotspot.inventoryId ? model.alarmsByComponentId?.[hotspot.inventoryId] : undefined;
            const portStatus: PortStatusInfo | undefined =
              hotspot.inventoryId ? portStatusByComponentId?.[hotspot.inventoryId] : undefined;
            const baseTitle = hotspot.metadata?.sourceName ?? hotspot.label;
            return (
              <button
                key={hotspot.id}
                type="button"
                disabled={!canSelect}
                title={portStatus ? `${baseTitle} — ${portStatus.interfaceName} ${PORT_STATUS_LABELS[portStatus.status]}` : baseTitle}
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
                  !showHotspotChrome
                    ? 'border-transparent bg-transparent focus-visible:border-cisco-blue/80 focus-visible:bg-cisco-blue/10'
                    : selected
                      ? 'border-cisco-blue bg-cisco-blue/20 shadow-[0_0_0_4px_rgba(0,124,186,0.25)]'
                      : canSelect
                        ? 'border-transparent bg-green-500/0 hover:border-cisco-blue/70 hover:bg-cisco-blue/10'
                        : 'border-gray-400/40 bg-gray-500/10'
                }`}
                style={percentBounds(hotspot, view)}
              >
                {portStatus && <PortStatusDot status={portStatus.status} />}
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
