import { useEffect, useRef, useState } from 'react';
import type { Alarm, AlarmWsMessage } from './types';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/alarms/ws`;
const MAX_BACKOFF_MS = 30_000;

export interface AlarmWebSocket {
  lastAlarm: Alarm | null;
  connected: boolean;
}

export function useAlarmWebSocket(): AlarmWebSocket {
  const [lastAlarm, setLastAlarm] = useState<Alarm | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1_000);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!mountedRef.current) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        backoffRef.current = 1_000;
        setConnected(true);
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        if (!mountedRef.current) return;
        try {
          const msg = JSON.parse(event.data) as AlarmWsMessage;
          if (msg.type === 'alarm' && msg.alarm) {
            setLastAlarm(msg.alarm);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        const delay = Math.min(backoffRef.current, MAX_BACKOFF_MS);
        backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);
        setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, []);

  return { lastAlarm, connected };
}
