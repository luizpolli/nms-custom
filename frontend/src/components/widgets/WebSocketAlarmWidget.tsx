import { useCallback, useState } from 'react';
import { useAlarmWebSocket } from '../../lib/ws';
import { Badge } from '../ui/Badge';
import type { Alarm, AlarmWsMessage } from '../../lib/types';

const MAX_FEED = 25;

function timeAgo(value?: string) {
  if (!value) return '—';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ago`;
}

export function WebSocketAlarmWidget() {
  const [feed, setFeed] = useState<Alarm[]>([]);
  const [hb, setHb] = useState<string | null>(null);

  const onMessage = useCallback((msg: AlarmWsMessage) => {
    if (msg.type === 'hb') {
      setHb(msg.ts ?? null);
    } else if (msg.type === 'alarm' && msg.alarm) {
      setFeed((prev) => [msg.alarm!, ...prev].slice(0, MAX_FEED));
    }
  }, []);

  const { connected } = useAlarmWebSocket(onMessage);

  return (
    <div className="flex flex-col h-full">
      {/* Status bar */}
      <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-1.5 text-xs dark:border-gray-800">
        <span
          className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`}
          title={connected ? 'Connected' : 'Disconnected'}
        />
        <span className="text-gray-500 dark:text-gray-400">
          {connected ? 'Live' : 'Reconnecting…'}
        </span>
        {hb && (
          <span className="ml-auto text-gray-400">hb {new Date(hb).toLocaleTimeString()}</span>
        )}
      </div>

      {/* Feed */}
      {feed.length === 0 ? (
        <div className="flex flex-1 items-center justify-center p-4 text-sm text-gray-400">
          Waiting for alarms…
        </div>
      ) : (
        <ul className="flex-1 divide-y divide-gray-100 overflow-auto dark:divide-gray-800">
          {feed.map((alarm, idx) => (
            <li
              key={`${alarm.id}-${idx}`}
              className="grid grid-cols-[auto,minmax(0,1fr),auto] items-center gap-2 px-3 py-2 text-sm"
            >
              <Badge variant={alarm.severity as never}>{alarm.severity}</Badge>
              <div className="min-w-0">
                <div className="truncate font-medium text-gray-800 dark:text-gray-100">
                  {alarm.source_host ?? alarm.source ?? 'unknown'}
                </div>
                <div className="truncate text-xs text-gray-500 dark:text-gray-400">{alarm.message}</div>
              </div>
              <span className="whitespace-nowrap text-xs text-gray-400">
                {timeAgo(alarm.last_seen ?? alarm.raised_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
