import { DEMO_ALARMS, DEMO_ALARM_SUMMARY, DEMO_ALARM_FILTERS } from './data/alarms';
import { DEMO_DEVICES } from './data/devices';
import { DEMO_CREDENTIALS, DEMO_SERVICES, DEMO_ASSURANCE_SERVICES, DEMO_SERVICE_ALERTS, DEMO_TOPOLOGY } from './data/network';
import {
  DEMO_EXECUTIVE_SUMMARY,
  DEMO_PERFORMANCE_SUMMARY,
  makeDemoAggregate,
  DEMO_ALARM_TRENDS,
  DEMO_KPI_TRENDS,
} from './data/dashboard';

type Handler = (url: string, params?: Record<string, string>) => unknown;

// URL → handler map. Order matters: more specific patterns first.
const HANDLERS: Array<[RegExp, Handler]> = [
  // Alarms
  [/^\/alarms\/summary$/,     () => DEMO_ALARM_SUMMARY],
  [/^\/alarms\/filters$/,     () => DEMO_ALARM_FILTERS],
  [/^\/alarms$/,              () => DEMO_ALARMS],

  // Devices
  [/^\/devices$/,             () => DEMO_DEVICES],

  // Credentials
  [/^\/credentials$/,         () => DEMO_CREDENTIALS],

  // Topology
  [/^\/topology\/graph$/,     () => DEMO_TOPOLOGY],

  // Services
  [/^\/services$/,             () => DEMO_SERVICES],

  // Assurance
  [/^\/assurance\/services$/,      () => DEMO_ASSURANCE_SERVICES],
  [/^\/assurance\/service-alerts$/, () => DEMO_SERVICE_ALERTS],

  // Dashboard
  [/^\/dashboard\/executive-summary$/, () => DEMO_EXECUTIVE_SUMMARY],

  // Performance
  [/^\/performance\/summary$/, () => DEMO_PERFORMANCE_SUMMARY],
  [
    /^\/performance\/devices\/([^/]+)\/kpis\/aggregate$/,
    (url, params) => {
      const match = url.match(/\/performance\/devices\/([^/]+)\/kpis\/aggregate/);
      const deviceId = match?.[1] ?? '';
      const kpiType  = params?.kpi_type ?? 'cpu_5min';
      return makeDemoAggregate(deviceId, kpiType);
    },
  ],

  // KPI / alarm trend endpoints used by dashboard widgets
  [/^\/dashboard\/alarm-trends$/, () => DEMO_ALARM_TRENDS],
  [/^\/dashboard\/kpi-trends$/,   () => DEMO_KPI_TRENDS],

  // Service health widget
  [/^\/services\/health$/, () => ({
    total: DEMO_SERVICES.length,
    healthy: DEMO_ASSURANCE_SERVICES.filter((s) => s.health_state === 'healthy').length,
    degraded: DEMO_ASSURANCE_SERVICES.filter((s) => s.health_state === 'degraded').length,
    impaired: DEMO_ASSURANCE_SERVICES.filter((s) => s.health_state === 'impaired').length,
  })],
];

export function matchDemoHandler(
  url: string | undefined,
  _method: string | undefined,
  params?: Record<string, string>,
): unknown | undefined {
  if (!url) return undefined;
  // Strip leading /api prefix if present
  const path = url.replace(/^\/api/, '');
  for (const [pattern, handler] of HANDLERS) {
    if (pattern.test(path)) {
      return handler(path, params);
    }
  }
  return undefined;
}
