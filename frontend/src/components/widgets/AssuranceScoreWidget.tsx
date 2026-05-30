import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';

interface AssuranceSummary {
  network_score: number;
  health_state: string;
}

function useAssuranceSummary() {
  return useQuery({
    queryKey: ['assurance', 'summary'],
    queryFn: async () => {
      const { data } = await api.get<AssuranceSummary>('/assurance/summary');
      return data;
    },
    refetchInterval: 30_000,
  });
}

function scoreColor(score: number): string {
  if (score >= 90) return '#22c55e'; // green-500
  if (score >= 75) return '#f59e0b'; // amber-500
  return '#ef4444';                  // red-500
}

function scoreBg(score: number): string {
  if (score >= 90) return 'text-green-600 dark:text-green-400';
  if (score >= 75) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

/** Simple SVG gauge (semi-circle) */
function Gauge({ score }: { score: number }) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const radius = 40;
  const cx = 60;
  const cy = 60;
  const circumference = Math.PI * radius; // half circle
  const dashOffset = circumference * (1 - clampedScore / 100);
  const color = scoreColor(clampedScore);

  return (
    <svg viewBox="0 0 120 70" className="w-full max-w-[160px]" aria-hidden="true">
      {/* Track */}
      <path
        d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
        fill="none"
        stroke="currentColor"
        strokeWidth="8"
        className="text-gray-200 dark:text-gray-700"
        strokeLinecap="round"
      />
      {/* Fill */}
      <path
        d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.5s ease' }}
      />
    </svg>
  );
}

export function AssuranceScoreWidget() {
  const { data, isLoading, error } = useAssuranceSummary();

  if (isLoading) return <div className="p-4 text-sm text-gray-500">Loading…</div>;
  if (error || !data) return <div className="p-4 text-sm text-red-500">Failed to load assurance score.</div>;

  const score = data.network_score ?? 0;

  return (
    <div className="flex flex-col items-center justify-center gap-1 p-4">
      <Gauge score={score} />
      <span className={`text-3xl font-bold ${scoreBg(score)}`}>{score}</span>
      <span className="text-xs text-gray-500 dark:text-gray-400 capitalize">{data.health_state ?? 'unknown'}</span>
    </div>
  );
}
