import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Activity,
  Bell,
  BookOpen,
  ClipboardList,
  FileText,
  FlaskConical,
  KeyRound,
  Layers,
  LayoutDashboard,
  Network,
  Package,
  Radar,
  RadioTower,
  Server,
  ShieldCheck,
  Terminal,
} from 'lucide-react';
import { PageIntroFloat } from '../ui/PageIntroFloat';

type GuideStep = {
  title: string;
  text: string;
};

type GuideConfig = {
  storageKey: string;
  title: string;
  icon: ReactNode;
  description: string;
  steps: GuideStep[];
};

const GUIDE_CONFIGS: Record<string, GuideConfig> = {
  '/': {
    storageKey: 'nms-route-guide-dashboard',
    title: 'Dashboard guide',
    icon: <LayoutDashboard className="h-4 w-4 text-cisco-blue" />,
    description: 'Use Dashboard as the NMS command center: check health, identify active risk, then drill into the section that owns the issue.',
    steps: [
      { title: 'Read health', text: 'Start with cards, alarm summary, and device status.' },
      { title: 'Find risk', text: 'Compare critical alarms, down devices, and KPI breaches.' },
      { title: 'Drill down', text: 'Open Devices, Alarms, Performance, or Assurance for details.' },
    ],
  },
  '/devices': {
    storageKey: 'nms-route-guide-devices',
    title: 'Devices guide',
    icon: <Server className="h-4 w-4 text-cisco-blue" />,
    description: 'Devices is the managed-node registry. Add nodes, assign access data, verify reachability, and keep operational status current.',
    steps: [
      { title: 'Register', text: 'Create or import devices with IP, platform, site, and role.' },
      { title: 'Validate', text: 'Verify credentials and polling reachability.' },
      { title: 'Operate', text: 'Use device detail, inventory, interfaces, KPIs, and alarms.' },
    ],
  },
  '/inventory': {
    storageKey: 'nms-route-guide-inventory',
    title: 'Inventory guide',
    icon: <Package className="h-4 w-4 text-cisco-blue" />,
    description: 'Inventory exposes collected hardware, software, module, and interface facts so operators can audit what is actually deployed.',
    steps: [
      { title: 'Collect', text: 'Run discovery or inventory collection from managed devices.' },
      { title: 'Review', text: 'Inspect serials, versions, modules, interfaces, and metadata.' },
      { title: 'Act', text: 'Use gaps to update records, credentials, polling, or lifecycle plans.' },
    ],
  },
  '/credentials': {
    storageKey: 'nms-route-guide-credentials',
    title: 'Credentials guide',
    icon: <KeyRound className="h-4 w-4 text-cisco-blue" />,
    description: 'Credentials stores reusable SNMP, CLI, and access profiles used by discovery, polling, inventory, and command workflows.',
    steps: [
      { title: 'Create profile', text: 'Define SNMP/CLI access once instead of per workflow.' },
      { title: 'Attach safely', text: 'Map profiles to device operations that need them.' },
      { title: 'Rotate', text: 'Update credentials centrally and retest affected devices.' },
    ],
  },
  '/performance': {
    storageKey: 'nms-route-guide-performance',
    title: 'Performance guide',
    icon: <Activity className="h-4 w-4 text-cisco-blue" />,
    description: 'Performance turns collected KPI samples into trend views for CPU, memory, interface utilization, drops, errors, and thresholds.',
    steps: [
      { title: 'Select scope', text: 'Choose device, interface, KPI, and time range.' },
      { title: 'Analyze trend', text: 'Look for sustained utilization, spikes, and threshold crossings.' },
      { title: 'Correlate', text: 'Compare with Alarms, Telemetry, and Assurance impact.' },
    ],
  },
  '/telemetry': {
    storageKey: 'nms-route-guide-telemetry',
    title: 'Telemetry guide',
    icon: <RadioTower className="h-4 w-4 text-cisco-blue" />,
    description: 'Telemetry tracks ingestion health and live signal flow from pollers, traps, syslog, gNMI, and streaming collectors.',
    steps: [
      { title: 'Check sources', text: 'Confirm active collectors and recent samples.' },
      { title: 'Inspect flow', text: 'Review ingestion status, lag, errors, and fanout.' },
      { title: 'Repair data', text: 'Fix source, credential, policy, or receiver issues.' },
    ],
  },
  '/alarms': {
    storageKey: 'nms-route-guide-alarms',
    title: 'Alarms guide',
    icon: <Bell className="h-4 w-4 text-cisco-blue" />,
    description: 'Alarms is the live fault console. Use it to triage severity, acknowledge ownership, suppress noise, and inspect enriched context.',
    steps: [
      { title: 'Prioritize', text: 'Filter by severity, status, device, and time.' },
      { title: 'Investigate', text: 'Open alarm detail for enrichment and related objects.' },
      { title: 'Control noise', text: 'Acknowledge, suppress, or tune rules in Settings.' },
    ],
  },
  '/assurance': {
    storageKey: 'nms-route-guide-assurance',
    title: 'Assurance guide',
    icon: <ShieldCheck className="h-4 w-4 text-cisco-blue" />,
    description: 'Assurance summarizes health and impact across devices, interfaces, services, topology, and active events.',
    steps: [
      { title: 'Score', text: 'Start with health score and impacted entities.' },
      { title: 'Explain', text: 'Use contributing alarms, KPIs, and topology context.' },
      { title: 'Resolve', text: 'Move to the owning section for corrective action.' },
    ],
  },
  '/monitoring-policies': {
    storageKey: 'nms-route-guide-monitoring-policies',
    title: 'Monitoring Policies guide',
    icon: <ClipboardList className="h-4 w-4 text-cisco-blue" />,
    description: 'Monitoring Policies define what the platform collects, how often it collects it, and which devices receive each policy.',
    steps: [
      { title: 'Choose metric set', text: 'Pick device health, interface, optical, GNSS, or custom MIB scope.' },
      { title: 'Set cadence', text: 'Balance freshness, load, and retention.' },
      { title: 'Assign', text: 'Apply policies to matching device groups or targets.' },
    ],
  },
  '/topology': {
    storageKey: 'nms-route-guide-topology',
    title: 'Topology guide',
    icon: <Network className="h-4 w-4 text-cisco-blue" />,
    description: 'Topology maps device relationships so operators can understand adjacency, dependency, and likely blast radius.',
    steps: [
      { title: 'Build graph', text: 'Use discovery and link data to generate relationships.' },
      { title: 'Inspect', text: 'Select nodes and links for neighbor context.' },
      { title: 'Correlate', text: 'Use topology while investigating alarms or service impact.' },
    ],
  },
  '/discovery': {
    storageKey: 'nms-route-guide-discovery',
    title: 'Discovery guide',
    icon: <Radar className="h-4 w-4 text-cisco-blue" />,
    description: 'Discovery scans networks, identifies reachable devices, and seeds inventory records for management.',
    steps: [
      { title: 'Define scope', text: 'Enter subnets, ranges, protocol, and credential profile.' },
      { title: 'Scan', text: 'Run discovery and review reachable candidates.' },
      { title: 'Promote', text: 'Import valid devices into the managed inventory.' },
    ],
  },
  '/mibs': {
    storageKey: 'nms-route-guide-mibs',
    title: 'MIBs guide',
    icon: <BookOpen className="h-4 w-4 text-cisco-blue" />,
    description: 'MIBs lets you upload, parse, and reference SNMP object definitions for polling, trap enrichment, and custom KPIs.',
    steps: [
      { title: 'Upload', text: 'Add vendor or platform MIB files.' },
      { title: 'Parse', text: 'Validate OIDs, names, and dependencies.' },
      { title: 'Use', text: 'Map objects into polling, thresholds, and alarm enrichment.' },
    ],
  },
  '/commands': {
    storageKey: 'nms-route-guide-commands',
    title: 'Commands guide',
    icon: <Terminal className="h-4 w-4 text-cisco-blue" />,
    description: 'Commands runs approved operational commands against devices and keeps execution history for audit and troubleshooting.',
    steps: [
      { title: 'Select command', text: 'Pick a saved command or create an approved template.' },
      { title: 'Target devices', text: 'Choose one device or a safe bulk scope.' },
      { title: 'Review output', text: 'Inspect results, failures, and run history.' },
    ],
  },
  '/ios': {
    storageKey: 'nms-route-guide-ios',
    title: 'IOS Versions guide',
    icon: <Layers className="h-4 w-4 text-cisco-blue" />,
    description: 'IOS Versions tracks software images and version posture across devices for lifecycle, compliance, and upgrade planning.',
    steps: [
      { title: 'Inventory versions', text: 'Review discovered platform and software versions.' },
      { title: 'Compare', text: 'Identify outliers, old releases, and unsupported images.' },
      { title: 'Plan', text: 'Use findings to prepare controlled upgrades.' },
    ],
  },
  '/reports': {
    storageKey: 'nms-route-guide-reports',
    title: 'Reports guide',
    icon: <FileText className="h-4 w-4 text-cisco-blue" />,
    description: 'Reports converts inventory, KPI, alarm, and service data into exportable operational documents.',
    steps: [
      { title: 'Pick report', text: 'Choose the report type and data scope.' },
      { title: 'Set period', text: 'Define time range, devices, filters, and format.' },
      { title: 'Export', text: 'Generate output for review, sharing, or audit.' },
    ],
  },
  '/lab': {
    storageKey: 'nms-route-guide-lab',
    title: 'Lab Health guide',
    icon: <FlaskConical className="h-4 w-4 text-cisco-blue" />,
    description: 'Lab Health checks local platform readiness so demos and test workflows do not fail because a service, worker, or integration is down.',
    steps: [
      { title: 'Check status', text: 'Review API, worker, database, receiver, and frontend health.' },
      { title: 'Find blockers', text: 'Look for stale checks, failed services, or missing dependencies.' },
      { title: 'Repair', text: 'Restart or reconfigure the failing component before testing.' },
    ],
  },
};

function routeKey(pathname: string) {
  if (pathname === '/') return '/';
  const firstSegment = `/${pathname.split('/').filter(Boolean)[0] ?? ''}`;
  return firstSegment;
}

function GuideDiagram({ config }: { config: GuideConfig }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr] md:items-stretch">
        {config.steps.map((step, index) => (
          <div key={step.title} className="contents">
            <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{step.title}</div>
              <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{step.text}</p>
            </div>
            {index < config.steps.length - 1 && (
              <div className="hidden items-center justify-center text-xl text-gray-400 md:flex">-&gt;</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export function RouteGuideFloat() {
  const { pathname } = useLocation();
  const [dismissedThisSession, setDismissedThisSession] = useState<Set<string>>(() => new Set());
  const [visible, setVisible] = useState(false);
  const key = routeKey(pathname);
  const config = GUIDE_CONFIGS[key];

  useEffect(() => {
    if (!config || typeof window === 'undefined') {
      setVisible(false);
      return;
    }
    const dismissedPermanently = window.localStorage.getItem(config.storageKey) === 'true';
    setVisible(!dismissedPermanently && !dismissedThisSession.has(config.storageKey));
  }, [config, dismissedThisSession]);

  const handleDismiss = ({ dontShowAgain }: { dontShowAgain: boolean }) => {
    if (!config || typeof window === 'undefined') return;
    if (dontShowAgain) window.localStorage.setItem(config.storageKey, 'true');
    setDismissedThisSession((current) => {
      const next = new Set(current);
      next.add(config.storageKey);
      return next;
    });
    setVisible(false);
  };

  const guide = useMemo(() => config, [config]);
  if (!guide || !visible) return null;

  return (
    <PageIntroFloat title={guide.title} icon={guide.icon} onDismiss={handleDismiss}>
      <p className="mb-3 text-gray-600 dark:text-gray-300">{guide.description}</p>
      <GuideDiagram config={guide} />
    </PageIntroFloat>
  );
}
