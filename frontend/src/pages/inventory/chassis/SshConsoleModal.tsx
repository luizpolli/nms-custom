import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

/**
 * Interactive SSH console. Streams an xterm.js terminal over a WebSocket to the
 * backend PTY proxy (`/api/console/{deviceId}`). Requires a live device with SSH
 * credentials; in example/demo mode (no deviceId) it shows a notice instead.
 */
export function SshConsoleModal({
  deviceId,
  deviceName,
  onClose,
}: {
  deviceId?: string;
  deviceName: string;
  onClose: () => void;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!deviceId || !hostRef.current) return;
    const term = new Terminal({
      convertEol: true,
      cursorBlink: true,
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
      fontSize: 13,
      theme: { background: '#0b0f17', foreground: '#d6deeb' },
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    fit.fit();

    const apiKey = window.localStorage.getItem('nms_api_key') ?? '';
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const params = new URLSearchParams({ token: apiKey, cols: String(term.cols), rows: String(term.rows) });
    const ws = new WebSocket(`${proto}://${window.location.host}/api/console/${deviceId}?${params.toString()}`);

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') term.write(event.data);
    };
    ws.onclose = () => term.write('\r\n\x1b[90m[session closed]\x1b[0m\r\n');
    ws.onerror = () => term.write('\r\n\x1b[31m[connection error]\x1b[0m\r\n');
    const sub = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) ws.send(data);
    });

    const onWindowResize = () => fit.fit();
    window.addEventListener('resize', onWindowResize);
    term.focus();

    return () => {
      window.removeEventListener('resize', onWindowResize);
      sub.dispose();
      ws.close();
      term.dispose();
    };
  }, [deviceId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`SSH console ${deviceName}`}
      onClick={onClose}
    >
      <div
        className="relative flex h-[80vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg bg-[#0b0f17] shadow-2xl ring-1 ring-gray-700"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="flex items-center justify-between gap-3 border-b border-gray-700 bg-gray-900 px-4 py-2">
          <div className="flex items-center gap-2 text-sm text-gray-200">
            <span className="font-semibold">SSH console</span>
            <span className="text-gray-400">— {deviceName}</span>
          </div>
          <button
            type="button"
            aria-label="Close console"
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-100"
          >
            <X className="h-5 w-5" />
          </button>
        </header>
        {deviceId ? (
          <div ref={hostRef} className="min-h-0 flex-1 p-2" />
        ) : (
          <div className="flex flex-1 items-center justify-center p-8 text-center text-sm text-gray-400">
            La consola SSH requiere un equipo en vivo. Abre Inventory →
            <span className="mx-1 font-semibold text-gray-200">Live Inventory</span>
            y selecciona un dispositivo con credenciales SSH.
          </div>
        )}
      </div>
    </div>
  );
}
