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

  // Single column for low-density cards (e.g. 2-4 ports), otherwise the real
  // cards use a two-column cage grid.
  const cols = ports.length <= 4 ? 1 : 2;
  // EPNM numbers ports bottom-to-top, so render the faceplate overlay reversed
  // (port 0 at the bottom of the vertical card).
  const overlayPorts = [...ports].reverse();

  // Vertical faceplate display box. Cards are ~9:1, so the rotated card is a
  // thin tall strip; cap the height so 48-port cards still fit the viewport.
  const faceHeight = Math.min(720, Math.max(360, ports.length * 26 + 120));
  const faceWidth = Math.max(64, Math.round(faceHeight * 0.12));

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

        <div className="flex flex-1 gap-6 overflow-auto p-6">
          {/* Vertical faceplate with per-port status overlay */}
          <div className="flex shrink-0 flex-col items-center gap-2">
            <div
              className="relative rounded-sm border border-gray-300 bg-gray-100 shadow-inner dark:border-gray-700 dark:bg-gray-800"
              style={{ width: faceWidth, height: faceHeight }}
            >
              {card.image && (
                <img
                  src={card.image}
                  alt={`${card.typeId} faceplate`}
                  draggable={false}
                  className="pointer-events-none absolute left-1/2 top-1/2 select-none"
                  style={{
                    width: faceHeight,
                    height: faceWidth,
                    transform: 'translate(-50%, -50%) rotate(90deg)',
                    objectFit: 'fill',
                  }}
                />
              )}
              <div
                className="absolute inset-0 grid gap-[3px] px-[10%] py-[7%]"
                style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
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
