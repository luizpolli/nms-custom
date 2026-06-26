import { useEffect } from 'react';
import { X } from 'lucide-react';
import type { PortStatus } from './portInventory';

const PORT_STATUS_ICONS: Record<PortStatus, string> = {
  up: '/chassis-icons/up.svg',
  down: '/chassis-icons/down.svg',
  'admin-down': '/chassis-icons/fi-admindown.svg',
};

const PORT_STATUS_LABELS: Record<PortStatus, string> = {
  up: 'up',
  down: 'down',
  'admin-down': 'admin down',
};

export type ZoomPort = {
  id: string;
  label: string;
  status?: PortStatus;
  /** Real cage position as fractions (0-1) of the faceplate, when mapped. */
  bounds?: { x: number; y: number; w: number; h: number };
};

export interface CardZoomData {
  /** Module model, e.g. "A9K-2T20GE-L" */
  typeId: string;
  /** Human label, e.g. "module 0/3/CPU0" */
  name: string;
  /** Card description, e.g. "20-Port GE + 2-Port 10GE Line Card" */
  description?: string;
  /** Path to the card faceplate SVG (stored horizontal) */
  image?: string;
  /**
   * Card display orientation in the chassis. True for tall/vertical chassis
   * (ASR9010): the SVG is rotated 90deg and ports stack in a 2-column grid.
   * False for horizontal chassis (ASR9006): the SVG renders as-is with ports
   * in a 2-row grid.
   */
  vertical: boolean;
  /** Faceplate aspect ratio (width/height) when ports carry real bounds. */
  aspect?: number;
  ports: ZoomPort[];
}

/**
 * EPNM-style line-card drill-down. The faceplate SVG is stored horizontal
 * (e.g. 2779x310) but the card seats vertically in the ASR9010 chassis, so we
 * rotate it 90deg to match the physical orientation and overlay per-port status
 * icons in a two-column grid (mirroring the real cage layout). A readable port
 * list sits alongside for label + state at a glance.
 */
export function CardZoomModal({ card, onClose }: { card: CardZoomData; onClose: () => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const ports = card.ports;
  const counts = ports.reduce(
    (acc, port) => {
      if (port.status) acc[port.status] += 1;
      else acc.unknown += 1;
      return acc;
    },
    { up: 0, down: 0, 'admin-down': 0, unknown: 0 } as Record<PortStatus | 'unknown', number>,
  );

  const vertical = card.vertical;
  // Single line for low-density cards (e.g. 2-4 ports), otherwise the real
  // cards use a two-deep cage grid (2 columns when vertical, 2 rows horizontal).
  const minorAxis = ports.length <= 4 ? 1 : 2;
  // EPNM numbers ports bottom-to-top on vertical cards (port 0 lowest); on
  // horizontal cards port 0 sits at the left, so keep natural order there.
  const overlayPorts = vertical ? [...ports].reverse() : ports;

  // Faceplate box. Cards are ~9:1 so one axis is a thin strip; cap the long
  // axis so 48-port cards still fit the viewport.
  const longAxis = Math.min(vertical ? 720 : 560, Math.max(320, ports.length * 24 + 120));
  const shortAxis = Math.max(60, Math.round(longAxis * 0.12));
  const faceWidth = vertical ? shortAxis : longAxis;
  const faceHeight = vertical ? longAxis : shortAxis;
  const gridStyle = vertical
    ? { gridTemplateColumns: `repeat(${minorAxis}, minmax(0, 1fr))` }
    : { gridTemplateRows: `repeat(${minorAxis}, minmax(0, 1fr))`, gridAutoFlow: 'column' as const };

  // When every port carries a real cage position, render the faceplate at its
  // true aspect ratio and place ports absolutely (mirrors the chassis view)
  // instead of the even-grid fallback.
  const hasBounds = !vertical && ports.length > 0 && ports.every((p) => p.bounds);
  const faceW = hasBounds ? 660 : faceWidth;
  const faceH = hasBounds
    ? Math.max(70, Math.round(660 / (card.aspect && card.aspect > 0 ? card.aspect : 5)))
    : faceHeight;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Card view ${card.typeId}`}
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl dark:bg-gray-900"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-gray-200 px-5 py-3 dark:border-gray-700">
          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-gray-900 dark:text-gray-100">{card.typeId}</h3>
            <p className="truncate text-xs text-gray-500 dark:text-gray-400">
              {card.name}
              {card.description ? ` — ${card.description}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-3 text-xs text-gray-600 dark:text-gray-300 sm:flex">
              <StatusTally icon={PORT_STATUS_ICONS.up} label="Up" value={counts.up} />
              <StatusTally icon={PORT_STATUS_ICONS.down} label="Down" value={counts.down} />
              <StatusTally icon={PORT_STATUS_ICONS['admin-down']} label="Admin" value={counts['admin-down']} />
            </div>
            <button
              type="button"
              aria-label="Close card view"
              onClick={onClose}
              className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-100"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </header>

        <div className={`flex flex-1 gap-6 overflow-auto p-6 ${vertical ? '' : 'flex-col'}`}>
          {/* Faceplate with per-port status overlay */}
          <div className="flex shrink-0 flex-col items-center gap-2">
            <div
              className="relative rounded-sm border border-gray-300 bg-gray-100 shadow-inner dark:border-gray-700 dark:bg-gray-800"
              style={{ width: faceW, height: faceH }}
            >
              {card.image && (
                <img
                  src={card.image}
                  alt={`${card.typeId} faceplate`}
                  draggable={false}
                  className="pointer-events-none absolute left-1/2 top-1/2 select-none"
                  style={
                    vertical
                      ? {
                          width: faceH,
                          height: faceW,
                          transform: 'translate(-50%, -50%) rotate(90deg)',
                          objectFit: 'fill',
                        }
                      : {
                          width: faceW,
                          height: faceH,
                          transform: 'translate(-50%, -50%)',
                          objectFit: 'fill',
                        }
                  }
                />
              )}
              {hasBounds ? (
                <div className="absolute inset-0">
                  {ports.map((port) => (
                    <div
                      key={port.id}
                      title={`${port.label}${port.status ? ` — ${PORT_STATUS_LABELS[port.status]}` : ''}`}
                      className={`absolute flex items-center justify-center rounded-[2px] border ${
                        port.status ? 'border-gray-500/60 bg-black/25' : 'border-gray-400/30 bg-black/10'
                      }`}
                      style={{
                        left: `${port.bounds!.x * 100}%`,
                        top: `${port.bounds!.y * 100}%`,
                        width: `${port.bounds!.w * 100}%`,
                        height: `${port.bounds!.h * 100}%`,
                      }}
                    >
                      {port.status && (
                        <img
                          src={PORT_STATUS_ICONS[port.status]}
                          alt=""
                          aria-hidden="true"
                          draggable={false}
                          className="h-2.5 w-2.5 object-contain sm:h-3 sm:w-3"
                        />
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div
                  className={`absolute inset-0 grid gap-[3px] ${vertical ? 'px-[10%] py-[7%]' : 'px-[7%] py-[10%]'}`}
                  style={gridStyle}
                >
                  {overlayPorts.map((port) => (
                    <div
                      key={port.id}
                      title={`${port.label}${port.status ? ` — ${PORT_STATUS_LABELS[port.status]}` : ''}`}
                      className={`flex items-center justify-center rounded-[2px] border ${
                        port.status
                          ? 'border-gray-500/60 bg-black/30'
                          : 'border-gray-400/30 bg-black/10'
                      }`}
                    >
                      {port.status && (
                        <img
                          src={PORT_STATUS_ICONS[port.status]}
                          alt=""
                          aria-hidden="true"
                          draggable={false}
                          className="h-2.5 w-2.5 object-contain sm:h-3 sm:w-3"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
            <span className="text-[10px] uppercase tracking-wide text-gray-400">Front view</span>
          </div>

          {/* Readable port list */}
          <div className="min-w-0 flex-1">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Ports ({ports.length})
            </p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {ports.map((port) => (
                <div
                  key={port.id}
                  className="flex items-center gap-2 rounded border border-gray-200 px-2 py-1 text-xs dark:border-gray-700"
                >
                  {port.status ? (
                    <img
                      src={PORT_STATUS_ICONS[port.status]}
                      alt=""
                      aria-label={`port ${PORT_STATUS_LABELS[port.status]}`}
                      draggable={false}
                      className="h-3.5 w-3.5 shrink-0 object-contain"
                    />
                  ) : (
                    <span className="h-3.5 w-3.5 shrink-0 rounded-full bg-gray-300 dark:bg-gray-600" />
                  )}
                  <span className="truncate font-mono text-gray-700 dark:text-gray-200" title={port.label}>
                    {port.label}
                  </span>
                </div>
              ))}
              {ports.length === 0 && (
                <p className="text-xs text-gray-400">No mapped ports on this card.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusTally({ icon, label, value }: { icon: string; label: string; value: number }) {
  return (
    <span className="inline-flex items-center gap-1">
      <img src={icon} alt="" className="h-3.5 w-3.5 object-contain" draggable={false} />
      {label} {value}
    </span>
  );
}
