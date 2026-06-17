import { DEV } from './devices';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function bucket(offsetMinutes: number) {
  return new Date(Date.now() - offsetMinutes * 60_000).toISOString();
}

function wave(i: number, base: number, amp: number, freq = 1) {
  return Math.round((base + amp * Math.sin((i * freq * Math.PI) / 12)) * 10) / 10;
}

// ─── Executive Summary ────────────────────────────────────────────────────────

export const DEMO_EXECUTIVE_SUMMARY = {
  generated_at: new Date().toISOString(),
  uptime_pct: 98.4,
  alarms_new_24h: 21,
  alarms_resolved_24h: 14,
  mttr_minutes: 38,
  top_offenders: [
    { device_id: DEV.NCS55_MTY,   device_name: 'ncs55a1-mty-core-01',   alarm_count: 7, cpu_avg: 62 },
    { device_id: DEV.ASR9010_3,   device_name: 'asr9010-gdl-pe-01',     alarm_count: 5, cpu_avg: null },
    { device_id: DEV.NCS560_CDMX, device_name: 'ncs560-cdmx-agg-01',   alarm_count: 4, cpu_avg: 87 },
    { device_id: DEV.ASR9010_1,   device_name: 'asr9010-cdmx-pe-01',    alarm_count: 3, cpu_avg: 44 },
    { device_id: DEV.ASR5K_1,     device_name: 'asr5000-cdmx-mobile-01', alarm_count: 2, cpu_avg: 31 },
  ],
  kpi_sparklines: {
    cpu_avg:  Array.from({ length: 24 }, (_, i) => wave(i, 55, 18)),
    mem_avg:  Array.from({ length: 24 }, (_, i) => wave(i, 62, 10, 0.7)),
    intf_avg: Array.from({ length: 24 }, (_, i) => wave(i, 48, 22, 1.3)),
  },
  daily_stats: [
    { label: 'Devices managed',   value: 15,    unit: null },
    { label: 'Uptime 24h',        value: '98.4', unit: '%' },
    { label: 'New alarms',        value: 21,    unit: null,  delta: 5 },
    { label: 'Resolved alarms',   value: 14,    unit: null,  delta: -3 },
    { label: 'MTTR',              value: 38,    unit: 'min', delta: -7 },
    { label: 'Active MPLS LSPs',  value: 12,    unit: null },
    { label: 'Services degraded', value: 3,     unit: null,  delta: 1 },
    { label: 'Avg CPU 5min',      value: 54.2,  unit: '%',   delta: 2.1 },
  ],
};

// ─── Performance Summary ──────────────────────────────────────────────────────

export const DEMO_PERFORMANCE_SUMMARY = {
  cpu_avg: 54.2,
  mem_avg: 63.8,
  top_devices: [
    { device_id: DEV.NCS560_CDMX, name: 'ncs560-cdmx-agg-01',    cpu_5min: 87 },
    { device_id: DEV.NCS55_MTY,   name: 'ncs55a1-mty-core-01',    cpu_5min: 62 },
    { device_id: DEV.ASR9010_1,   name: 'asr9010-cdmx-pe-01',     cpu_5min: 44 },
    { device_id: DEV.NCS55_CDMX,  name: 'ncs55a1-cdmx-core-01',  cpu_5min: 38 },
    { device_id: DEV.ASR5K_1,     name: 'asr5000-cdmx-mobile-01', cpu_5min: 31 },
  ],
};

// ─── Performance Aggregate (12 buckets × 5m = 1 hour) ────────────────────────

export function makeDemoAggregate(deviceId: string, kpiType: string) {
  const bases: Record<string, Record<string, number>> = {
    [DEV.NCS560_CDMX]: { cpu_5min: 86, cpu_1min: 88, mem_used_pct: 71, if_in_octets_rate: 38e6, if_out_octets_rate: 32e6 },
    [DEV.NCS55_MTY]:   { cpu_5min: 60, cpu_1min: 62, mem_used_pct: 68, if_in_octets_rate: 55e6, if_out_octets_rate: 48e6 },
    [DEV.ASR9010_1]:   { cpu_5min: 44, cpu_1min: 46, mem_used_pct: 60, if_in_octets_rate: 70e6, if_out_octets_rate: 65e6 },
    [DEV.NCS55_CDMX]:  { cpu_5min: 38, cpu_1min: 40, mem_used_pct: 66, if_in_octets_rate: 72e6, if_out_octets_rate: 68e6 },
    [DEV.ASR5K_1]:     { cpu_5min: 31, cpu_1min: 33, mem_used_pct: 55, if_in_octets_rate: 88e6, if_out_octets_rate: 82e6 },
  };
  const base = (bases[deviceId]?.[kpiType] ?? 50);
  const amp = base * 0.12;
  return Array.from({ length: 12 }, (_, i) => {
    const avg = wave(i, base, amp);
    return {
      ts:  bucket((11 - i) * 5),
      avg,
      min: Math.round((avg - amp * 0.6) * 10) / 10,
      max: Math.round((avg + amp * 0.6) * 10) / 10,
    };
  });
}

// ─── Dashboard alarm trends (NOCBoard / other pages) ─────────────────────────

export const DEMO_ALARM_TRENDS = Array.from({ length: 48 }, (_, i) => ({
  ts:      bucket((47 - i) * 30),
  raised:  Math.round(Math.max(0, 3 + 5 * Math.sin((i * Math.PI) / 12))),
  cleared: Math.round(Math.max(0, 2 + 4 * Math.sin((i * Math.PI) / 12 + 1))),
}));

// ─── NOCBoard / assurance KPI trends ─────────────────────────────────────────

export const DEMO_KPI_TRENDS = Array.from({ length: 24 }, (_, i) => ({
  ts:       bucket((23 - i) * 60),
  cpu_avg:  wave(i, 55, 18),
  mem_avg:  wave(i, 62, 10, 0.7),
  intf_avg: wave(i, 48, 22, 1.3),
}));
