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
import {
  DEMO_TELEMETRY_HEALTH,
  DEMO_TELEMETRY_COLLECTORS,
  DEMO_TELEMETRY_SUBSCRIPTIONS,
  DEMO_TELEMETRY_SENSOR_PATHS,
  DEMO_COMMANDS,
  DEMO_IOS_EOL_REPORT,
  getDemoIOSVersions,
  DEMO_MONITORING_POLICIES,
  DEMO_MONITORING_PRESETS,
  getDemoDeviceInventory,
} from './data/operations';

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

  // Telemetry
  [/^\/telemetry\/health$/,        () => DEMO_TELEMETRY_HEALTH],
  [/^\/telemetry\/collectors$/,    () => DEMO_TELEMETRY_COLLECTORS],
  [/^\/telemetry\/subscriptions$/, () => DEMO_TELEMETRY_SUBSCRIPTIONS],
  [/^\/telemetry\/sensor-paths$/,  () => DEMO_TELEMETRY_SENSOR_PATHS],

  // Commands
  [/^\/commands$/, () => DEMO_COMMANDS],

  // IOS versions — more specific first
  [/^\/ios\/eol-report$/, () => DEMO_IOS_EOL_REPORT],
  [
    /^\/ios\/devices\/([^/]+)\/versions$/,
    (url) => {
      const match = url.match(/\/ios\/devices\/([^/]+)\/versions/);
      return getDemoIOSVersions(match?.[1] ?? '');
    },
  ],

  // Monitoring policies — presets before list
  [/^\/monitoring-policies\/presets$/, () => DEMO_MONITORING_PRESETS],
  [/^\/monitoring-policies$/,         () => DEMO_MONITORING_POLICIES],

  // Per-device inventory — must come before /devices$ to avoid partial match
  [
    /^\/devices\/([^/]+)\/inventory$/,
    (url) => {
      const match = url.match(/\/devices\/([^/]+)\/inventory/);
      return getDemoDeviceInventory(match?.[1] ?? '');
    },
  ],

  // AI Ops assistant — canned, citation-bearing answer so the panel renders
  // a realistic example instead of falling through to the generic
  // "{ ok: true, demo: true }" POST stub (which lacks `citations`/`answer`
  // and breaks normalizeAssistantAnswer's `.map()` call).
  [
    /^\/ai-ops\/assistant\/ask$/,
    () => ({
      question: 'What is happening with critical links right now?',
      answer:
        'Interface TenGigE0/0/0/24 on ncs55a1-mty-core-01 is down due to carrier loss [alarm:alarm-0001]. ' +
        'This is advisory-only synthetic data — demo mode never calls a real LLM provider.',
      citations: [
        {
          source_type: 'alarm',
          object_id: 'alarm:alarm-0001',
          label: 'Interface TenGigE0/0/0/24 is DOWN — carrier loss detected',
          timestamp: new Date().toISOString(),
          detail: 'severity=critical state=active source=ncs55a1-mty-core-01',
        },
      ],
      provider: 'demo',
      advisory_only: true,
      rejected_reason: null,
      generated_at: new Date().toISOString(),
    }),
  ],
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
