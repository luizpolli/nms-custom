import { lazy, Suspense, type ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { ErrorBoundary } from './components/ErrorBoundary';
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
const ServicesPage = lazySafe(
  () => import('./pages/services/ServicesPage').then((m) => pickExport(m, 'ServicesPage')),
  'ServicesPage',
);
const AIOpsPage = lazySafe(
  () => import('./pages/aiops/AIOpsPage').then((m) => pickExport(m, 'AIOpsPage')),
  'AIOpsPage',
);
const LabHealthPage = lazySafe(
  () => import('./pages/lab/LabHealthPage').then((m) => pickExport(m, 'LabHealthPage')),
  'LabHealthPage',
);

function PageFallback() {
  return (
    <div className="flex h-full items-center justify-center">
      <Spinner />
    </div>
  );
}

function Guarded({ children, name }: { children: React.ReactNode; name: string }) {
  return <ErrorBoundary fallbackTitle={`Error loading ${name}`}>{children}</ErrorBoundary>;
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Guarded name="Dashboard"><Dashboard /></Guarded>} />
          <Route path="devices" element={<Guarded name="Devices"><DevicesPage /></Guarded>} />
          <Route path="devices/:id" element={<Guarded name="Device Detail"><DeviceDetailPage /></Guarded>} />
          <Route path="inventory" element={<Guarded name="Inventory"><InventoryPage /></Guarded>} />
          <Route path="credentials" element={<Guarded name="Credentials"><CredentialsPage /></Guarded>} />
          <Route path="performance" element={<Guarded name="Performance"><PerformancePage /></Guarded>} />
          <Route path="telemetry" element={<Guarded name="Telemetry"><TelemetryPage /></Guarded>} />
          <Route path="alarms" element={<Guarded name="Alarms"><AlarmsPage /></Guarded>} />
          <Route path="assurance" element={<Guarded name="Assurance"><AssurancePage /></Guarded>} />
          <Route path="services" element={<Guarded name="Services"><ServicesPage /></Guarded>} />
          <Route path="ai-ops" element={<Guarded name="AI Ops"><AIOpsPage /></Guarded>} />
          <Route path="lab" element={<Guarded name="Lab Health"><LabHealthPage /></Guarded>} />
          <Route path="alarm-rules" element={<Guarded name="Alarm Rules"><AlarmRulesPage /></Guarded>} />
          <Route path="monitoring-policies" element={<Guarded name="Monitoring Policies"><MonitoringPoliciesPage /></Guarded>} />
          <Route path="topology" element={<Guarded name="Topology"><TopologyPage /></Guarded>} />
          <Route path="discovery" element={<Guarded name="Discovery"><DiscoveryPage /></Guarded>} />
          <Route path="mibs" element={<Guarded name="MIBs"><MIBsPage /></Guarded>} />
          <Route path="commands" element={<Guarded name="Commands"><CommandsPage /></Guarded>} />
          <Route path="ios" element={<Guarded name="IOS Versions"><IOSPage /></Guarded>} />
          <Route path="reports" element={<Guarded name="Reports"><ReportsPage /></Guarded>} />
          <Route path="settings" element={<Guarded name="Settings"><Settings /></Guarded>} />
          <Route path="404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
