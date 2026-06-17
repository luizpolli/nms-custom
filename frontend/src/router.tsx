import { lazy, Suspense, type ComponentType } from 'react';
import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { useModuleControls } from './components/layout/ModuleControlProvider';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Spinner } from './components/ui/Spinner';
import { moduleByKey, type ModuleKey } from './lib/moduleControls';

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
const DashboardExecutive = lazySafe(
  () => import('./pages/DashboardExecutive').then((m) => pickExport(m, 'DashboardExecutive')),
  'DashboardExecutive',
);
const NOCBoard = lazySafe(
  () => import('./pages/NOCBoard').then((m) => pickExport(m, 'NOCBoard')),
  'NOCBoard',
);
const CustomDashboardPage = lazySafe(
  () => import('./pages/dashboard/CustomDashboardPage').then((m) => pickExport(m, 'CustomDashboardPage')),
  'CustomDashboardPage',
);
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
const AlarmsHistoryPage = lazySafe(
  () => import('./pages/alarms/AlarmsHistoryPage').then((m) => pickExport(m, 'AlarmsHistoryPage')),
  'AlarmsHistoryPage',
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
const SystemAdminPage = lazySafe(
  () => import('./pages/system/SystemAdminPage').then((m) => pickExport(m, 'SystemAdminPage')),
  'SystemAdminPage',
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

function ModuleDisabled({ moduleKey }: { moduleKey: ModuleKey }) {
  const module = moduleByKey[moduleKey];
  return (
    <div className="flex h-full items-center justify-center">
      <div className="max-w-lg rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-3 flex items-center gap-3 text-gray-900 dark:text-gray-100">
          <span className="text-cisco-blue">{module.icon}</span>
          <h2 className="text-lg font-semibold">{module.label} is disabled</h2>
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          This module is currently turned off for this deployment. Enable it from Settings, under Modules / Feature Control.
        </p>
        <Link
          to="/settings?section=modules"
          className="mt-4 inline-flex rounded-md bg-cisco-blue px-4 py-2 text-sm font-medium text-white hover:bg-cisco-blue-dark"
        >
          Open module settings
        </Link>
      </div>
    </div>
  );
}

function ModuleGate({ moduleKey, children }: { moduleKey: ModuleKey; children: React.ReactNode }) {
  const { loading, isEnabled } = useModuleControls();
  if (loading) return <PageFallback />;
  if (!isEnabled(moduleKey)) return <ModuleDisabled moduleKey={moduleKey} />;
  return <>{children}</>;
}

function ModuleRoute({ moduleKey, name, children }: { moduleKey: ModuleKey; name: string; children: React.ReactNode }) {
  return (
    <Guarded name={name}>
      <ModuleGate moduleKey={moduleKey}>{children}</ModuleGate>
    </Guarded>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<ModuleRoute moduleKey="dashboard" name="Dashboard"><Dashboard /></ModuleRoute>} />
          <Route path="dashboard/executive" element={<ModuleRoute moduleKey="dashboard" name="Executive Summary"><DashboardExecutive /></ModuleRoute>} />
          <Route path="dashboard/noc" element={<ModuleRoute moduleKey="dashboard" name="NOC Board"><NOCBoard /></ModuleRoute>} />
          <Route path="devices" element={<ModuleRoute moduleKey="devices" name="Devices"><DevicesPage /></ModuleRoute>} />
          <Route path="devices/:id" element={<ModuleRoute moduleKey="devices" name="Device Detail"><DeviceDetailPage /></ModuleRoute>} />
          <Route path="inventory" element={<ModuleRoute moduleKey="inventory" name="Inventory"><InventoryPage /></ModuleRoute>} />
          <Route path="credentials" element={<ModuleRoute moduleKey="credentials" name="Credentials"><CredentialsPage /></ModuleRoute>} />
          <Route path="performance" element={<ModuleRoute moduleKey="performance" name="Performance"><PerformancePage /></ModuleRoute>} />
          <Route path="telemetry" element={<ModuleRoute moduleKey="telemetry" name="Telemetry"><TelemetryPage /></ModuleRoute>} />
          <Route path="alarms" element={<ModuleRoute moduleKey="alarms" name="Alarms"><AlarmsPage /></ModuleRoute>} />
          <Route path="alarms/history" element={<ModuleRoute moduleKey="alarms" name="Alarms History"><AlarmsHistoryPage /></ModuleRoute>} />
          <Route path="assurance" element={<ModuleRoute moduleKey="assurance" name="Assurance"><AssurancePage /></ModuleRoute>} />
          <Route path="services" element={<ModuleRoute moduleKey="services" name="Services"><ServicesPage /></ModuleRoute>} />
          <Route path="ai-ops" element={<ModuleRoute moduleKey="ai_ops" name="AI Ops"><AIOpsPage /></ModuleRoute>} />
          <Route path="system-admin" element={<ModuleRoute moduleKey="system_admin" name="System Admin"><SystemAdminPage /></ModuleRoute>} />
          <Route path="dashboard/custom" element={<Guarded name="Custom Dashboard"><CustomDashboardPage /></Guarded>} />
          <Route path="lab" element={<Navigate to="/settings?section=labOperations" replace />} />
          <Route path="alarm-rules" element={<Navigate to="/settings?section=alarmsEvents" replace />} />
          <Route path="monitoring-policies" element={<ModuleRoute moduleKey="monitoring_policies" name="Monitoring Policies"><MonitoringPoliciesPage /></ModuleRoute>} />
          <Route path="topology" element={<ModuleRoute moduleKey="topology" name="Topology"><TopologyPage /></ModuleRoute>} />
          <Route path="discovery" element={<ModuleRoute moduleKey="discovery" name="Discovery"><DiscoveryPage /></ModuleRoute>} />
          <Route path="mibs" element={<Navigate to="/settings?section=networkDevices" replace />} />
          <Route path="commands" element={<ModuleRoute moduleKey="commands" name="Commands"><CommandsPage /></ModuleRoute>} />
          <Route path="ios" element={<ModuleRoute moduleKey="ios" name="IOS Versions"><IOSPage /></ModuleRoute>} />
          <Route path="reports" element={<ModuleRoute moduleKey="reports" name="Reports"><ReportsPage /></ModuleRoute>} />
          <Route path="settings" element={<Guarded name="Settings"><Settings /></Guarded>} />
          <Route path="404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
