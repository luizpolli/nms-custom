import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { EmptyState } from '../ui/EmptyState';

interface TrendBucket {
  hour: string; // ISO timestamp for bucket start
  count: number;
}

interface AlarmTrendResponse {
  buckets: TrendBucket[];
  window_hours: number;
}

function useAlarmTrend() {
  return useQuery({
    queryKey: ['alarms', 'trend-24h'],
    queryFn: async () => {
      const { data } = await api.get<AlarmTrendResponse>('/alarms/trend', {
        params: { hours: 24, bucket: 'hour' },
      });
      return data;
    },
    refetchInterval: 60_000,
    retry: 1,
  });
}

function formatHour(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return `${String(d.getHours()).padStart(2, '0')}:00`;
}

/** Pure SVG sparkline — no external dependencies */
function Sparkline({ buckets }: { buckets: TrendBucket[] }) {
  if (!buckets.length) return null;

  const W = 300;
  const H = 60;
  const PADDING = { top: 4, right: 4, bottom: 20, left: 28 };
  const innerW = W - PADDING.left - PADDING.right;
  const innerH = H - PADDING.top - PADDING.bottom;

  const counts = buckets.map((b) => b.count);
  const maxCount = Math.max(...counts, 1);

  const points = buckets.map((b, i) => {
    const x = PADDING.left + (i / (buckets.length - 1 || 1)) * innerW;
    const y = PADDING.top + innerH - (b.count / maxCount) * innerH;
    return { x, y, b };
  });

  const polyline = points.map((p) => `${p.x},${p.y}`).join(' ');

  // Area fill path
  const areaPath =
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ') +
    ` L${points[points.length - 1].x},${H - PADDING.bottom} L${PADDING.left},${H - PADDING.bottom} Z`;

  // Show every 4th label to avoid clutter
  const step = Math.max(1, Math.floor(buckets.length / 6));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="trend-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {/* Y-axis ticks */}
      {[0, 0.5, 1].map((frac) => {
        const y = PADDING.top + innerH * (1 - frac);
        return (
          <g key={frac}>
            <line
              x1={PADDING.left}
              x2={W - PADDING.right}
              y1={y}
              y2={y}
              stroke="currentColor"
              strokeWidth="0.5"
              className="text-gray-200 dark:text-gray-700"
            />
            <text
              x={PADDING.left - 4}
              y={y + 3}
              textAnchor="end"
              fontSize="6"
              className="fill-gray-400 dark:fill-gray-500"
            >
              {Math.round(maxCount * frac)}
            </text>
          </g>
        );
      })}

      {/* Area */}
      <path d={areaPath} fill="url(#trend-grad)" />

      {/* Line */}
      <polyline
        points={polyline}
        fill="none"
        stroke="#3b82f6"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {/* X labels */}
      {points
        .filter((_, i) => i % step === 0 || i === points.length - 1)
        .map(({ x, b }) => (
          <text
            key={b.hour}
            x={x}
            y={H - 4}
            textAnchor="middle"
            fontSize="6"
            className="fill-gray-400 dark:fill-gray-500"
          >
            {formatHour(b.hour)}
          </text>
        ))}
    </svg>
  );
}

export function AlarmTrendWidget() {
  const { data, isLoading, error } = useAlarmTrend();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error) return <div className="p-4 text-sm text-red-500">Alarm trend data unavailable.</div>;

  const buckets = data?.buckets ?? [];
  if (!buckets.length) return <EmptyState message="No trend data for the last 24h" />;

  const total = buckets.reduce((s, b) => s + b.count, 0);
  const peak = Math.max(...buckets.map((b) => b.count));

  return (
    <div className="flex flex-col gap-2 p-3">
      <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>Last 24h · {buckets.length} buckets</span>
        <span>Total: <strong className="text-gray-700 dark:text-gray-200">{total}</strong> · Peak: <strong className="text-gray-700 dark:text-gray-200">{peak}</strong></span>
      </div>
      <Sparkline buckets={buckets} />
    </div>
  );
}
