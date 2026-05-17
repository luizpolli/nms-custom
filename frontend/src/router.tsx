import { lazy, Suspense, type ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { Spinner } from './components/ui/Spinner';

interface PlaceholderProps {
  name: string;
}

function Placeholder({ name }: PlaceholderProps) {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-6 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
        <h2 className="mb-1 text-lg font-semibold">Page unavailable: {name}</h2>
        <p className="text-sm">
          Module failed to load. Verify the file exists and the build is up to date.
        </p>
      </div>
    </div>
  );
}

function lazySafe(
  loader: () => Promise<{ default: ComponentType }>,
  name: string,
): ComponentType {
  return lazy(() =>
    loader().catch((err) => {
      console.error(`Failed to load ${name}:`, err);
      return { default: () => <Placeholder name={name} /> };
    }),
  );
}

const Dashboard = lazySafe(() => import('./pages/Dashboard'), 'Dashboard');
const NotFound = lazySafe(() => import('./pages/NotFound'), 'NotFound');
const Settings = lazySafe(() => import('./pages/Settings'), 'Settings');

const DevicesPage = lazySafe(
  () => import('./pages/devices/DevicesPage').then((m) => pickExport(m, 'DevicesPage')),
  'DevicesPage',
);
const DeviceDetailPage = lazySafe(
  () => import('./pages/devices/DeviceDetailPage').then((m) => pickExport(m, 'DeviceDetailPage')),
  'DeviceDetailPage',
);
const InventoryPage = lazySafe(
  () => import('./pages/inventory/InventoryPage').then((m) => pickExport(m, 'InventoryPage')),
  'InventoryPage',
);
const CredentialsPage = lazySafe(
  () => import('./pages/credentials/CredentialsPage').then((m) => pickExport(m, 'CredentialsPage')),
  'CredentialsPage',
);
const PerformancePage = lazySafe(
  () => import('./pages/performance/PerformancePage').then((m) => pickExport(m, 'PerformancePage')),
  'PerformancePage',
);
const AlarmsPage = lazySafe(
  () => import('./pages/alarms/AlarmsPage').then((m) => pickExport(m, 'AlarmsPage')),
  'AlarmsPage',
);
const AlarmRulesPage = lazySafe(
  () => import('./pages/alarms/AlarmRulesPage').then((m) => pickExport(m, 'AlarmRulesPage')),
  'AlarmRulesPage',
);
const MonitoringPoliciesPage = lazySafe(
  () => import('./pages/monitoring/MonitoringPoliciesPage').then((m) => pickExport(m, 'MonitoringPoliciesPage')),
  'MonitoringPoliciesPage',
);

function pickExport(m: Record<string, unknown>, name: string): { default: ComponentType } {
  const cmp = (m.default ?? m[name]) as ComponentType | undefined;
  if (!cmp) throw new Error(`Module has neither default nor named export: ${name}`);
  return { default: cmp };
}

const TopologyPage = lazySafe(
  () => import('./pages/topology/TopologyPage').then((m) => pickExport(m, 'TopologyPage')),
  'TopologyPage',
);
const DiscoveryPage = lazySafe(
  () => import('./pages/discovery/DiscoveryPage').then((m) => pickExport(m, 'DiscoveryPage')),
  'DiscoveryPage',
);
const MIBsPage = lazySafe(
  () => import('./pages/mibs/MIBsPage').then((m) => pickExport(m, 'MIBsPage')),
  'MIBsPage',
);
const CommandsPage = lazySafe(
  () => import('./pages/commands/CommandsPage').then((m) => pickExport(m, 'CommandsPage')),
  'CommandsPage',
);
const IOSPage = lazySafe(
  () => import('./pages/ios/IOSPage').then((m) => pickExport(m, 'IOSPage')),
  'IOSPage',
);
const ReportsPage = lazySafe(
  () => import('./pages/reports/ReportsPage').then((m) => pickExport(m, 'ReportsPage')),
  'ReportsPage',
);
const TelemetryPage = lazySafe(
  () => import('./pages/performance/TelemetryPage').then((m) => pickExport(m, 'TelemetryPage')),
  'TelemetryPage',
);
const AssurancePage = lazySafe(
  () => import('./pages/assurance/AssurancePage').then((m) => pickExport(m, 'AssurancePage')),
  'AssurancePage',
);

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <Spinner />
    </div>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="devices/:id" element={<DeviceDetailPage />} />
          <Route path="inventory" element={<InventoryPage />} />
          <Route path="credentials" element={<CredentialsPage />} />
          <Route path="performance" element={<PerformancePage />} />
          <Route path="telemetry" element={<TelemetryPage />} />
          <Route path="alarms" element={<AlarmsPage />} />
          <Route path="assurance" element={<AssurancePage />} />
          <Route path="alarm-rules" element={<AlarmRulesPage />} />
          <Route path="monitoring-policies" element={<MonitoringPoliciesPage />} />
          <Route path="topology" element={<TopologyPage />} />
          <Route path="discovery" element={<DiscoveryPage />} />
          <Route path="mibs" element={<MIBsPage />} />
          <Route path="commands" element={<CommandsPage />} />
          <Route path="ios" element={<IOSPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="settings" element={<Settings />} />
          <Route path="404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
