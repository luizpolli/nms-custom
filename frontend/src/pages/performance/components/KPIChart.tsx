import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

export interface KPIDataPoint {
  ts: string;
  avg: number;
  min: number;
  max: number;
}

interface KPIChartProps {
  data: KPIDataPoint[];
  kpiType: string;
  unit?: string;
}

const KPI_LABEL_MAP: Record<string, string> = {
  cpu_5min: 'CPU 5 min (%)',
  cpu_1min: 'CPU 1 min (%)',
  mem_used_pct: 'Memory (%)',
  if_in_octets_rate: 'Inbound traffic (bps)',
  if_out_octets_rate: 'Outbound traffic (bps)',
};

function formatTs(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

export function KPIChart({ data, kpiType, unit }: KPIChartProps) {
  const label = KPI_LABEL_MAP[kpiType] ?? kpiType;
  const yUnit = unit ?? (kpiType.includes('pct') || kpiType.includes('cpu') ? '%' : '');

  const chartData = data.map((d) => ({
    ...d,
    band: [d.min, d.max] as [number, number],
    ts_fmt: formatTs(d.ts),
  }));

  return (
    <div className="w-full h-64">
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</p>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
          <XAxis dataKey="ts_fmt" tick={{ fontSize: 10 }} />
          <YAxis
            unit={yUnit}
            tick={{ fontSize: 10 }}
            domain={['auto', 'auto']}
          />
          <Tooltip
            formatter={(value: number, name: string) => [`${value}${yUnit}`, name]}
            labelFormatter={(l: string) => `Time: ${l}`}
          />
          <Area
            dataKey="band"
            fill="#3b82f6"
            fillOpacity={0.15}
            stroke="none"
            name="Min-max range"
          />
          <Line
            type="monotone"
            dataKey="avg"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="Average"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
