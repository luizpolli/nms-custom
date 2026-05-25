import { useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info, X } from 'lucide-react';

type Position = {
  x: number;
  y: number;
};

const WINDOW_WIDTH = 320;
const WINDOW_HEIGHT = 160;
const EDGE_PADDING = 16;

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function fallbackPosition() {
  if (typeof window === 'undefined') return { x: EDGE_PADDING, y: EDGE_PADDING };
  return {
    x: Math.max(EDGE_PADDING, (window.innerWidth - WINDOW_WIDTH) / 2),
    y: Math.max(EDGE_PADDING, Math.min(160, (window.innerHeight - WINDOW_HEIGHT) / 2)),
  };
}

function positionFromButton(button: HTMLButtonElement | null) {
  if (!button || typeof window === 'undefined') return fallbackPosition();

  const rect = button.getBoundingClientRect();
  const maxX = Math.max(EDGE_PADDING, window.innerWidth - WINDOW_WIDTH - EDGE_PADDING);
  const maxY = Math.max(EDGE_PADDING, window.innerHeight - WINDOW_HEIGHT - EDGE_PADDING);
  let x = rect.right + 8;
  if (x + WINDOW_WIDTH > window.innerWidth - EDGE_PADDING) {
    x = rect.left - WINDOW_WIDTH - 8;
  }

  return {
    x: clamp(x, EDGE_PADDING, maxX),
    y: clamp(rect.top, EDGE_PADDING, maxY),
  };
}

export function InfoFloat({ title, description }: { title: string; description?: string }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<Position>(() => fallbackPosition());
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const closeTimer = useRef<number | null>(null);

  const clearCloseTimer = () => {
    if (closeTimer.current == null) return;
    window.clearTimeout(closeTimer.current);
    closeTimer.current = null;
  };

  const show = () => {
    clearCloseTimer();
    setPosition(positionFromButton(buttonRef.current));
    setOpen(true);
  };

  const scheduleClose = () => {
    clearCloseTimer();
    closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };

  return (
    <span className="inline-flex">
      <button
        ref={buttonRef}
        type="button"
        className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-cisco-blue/10 text-cisco-blue hover:bg-cisco-blue/20 focus:bg-cisco-blue/20"
        aria-label={`Info about ${title}`}
        aria-expanded={open}
        onMouseEnter={show}
        onMouseLeave={scheduleClose}
        onFocus={show}
        onBlur={scheduleClose}
        onClick={() => (open ? setOpen(false) : show())}
      >
        <Info className="h-3 w-3" />
      </button>

      {open && createPortal(
        <div
          className="fixed z-[9999] w-80 rounded-lg border border-gray-200 bg-white text-xs shadow-2xl dark:border-gray-700 dark:bg-gray-900"
          style={{ left: position.x, top: position.y }}
          role="dialog"
          aria-label={`Info about ${title}`}
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
        >
          <div className="flex items-center justify-between gap-3 rounded-t-lg border-b border-gray-100 px-3 py-2 dark:border-gray-800">
            <span className="font-semibold text-gray-900 dark:text-gray-100">{title}</span>
            <button
              type="button"
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
              aria-label="Close info"
              onClick={() => setOpen(false)}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="p-3 text-gray-600 dark:text-gray-300">{description || 'No description provided.'}</div>
        </div>,
        document.body,
      )}
    </span>
  );
}
