import {
  Activity,
  Bell,
  Bot,
  ClipboardList,
  FileText,
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
  Waypoints,
} from 'lucide-react';
import type { ReactNode } from 'react';

export type ModuleKey =
  | 'dashboard'
  | 'devices'
  | 'inventory'
  | 'credentials'
  | 'performance'
  | 'telemetry'
  | 'alarms'
  | 'assurance'
  | 'services'
  | 'ai_ops'
  | 'monitoring_policies'
  | 'topology'
  | 'discovery'
  | 'commands'
  | 'ios'
  | 'reports';

export type ModuleControlSettings = Record<ModuleKey, boolean>;

export interface ModuleMeta {
  key: ModuleKey;
  label: string;
  route: string;
  description: string;
  icon: ReactNode;
  group: 'Core' | 'Operations' | 'Automation' | 'Analytics';
}

export const MODULE_DEFAULTS: ModuleControlSettings = {
  dashboard: true,
  devices: true,
  inventory: true,
  credentials: true,
  performance: true,
  telemetry: true,
  alarms: true,
  assurance: true,
  services: true,
  ai_ops: true,
  monitoring_policies: true,
  topology: true,
  discovery: true,
  commands: true,
  ios: true,
  reports: true,
};

export const MODULES: ModuleMeta[] = [
  { key: 'dashboard', label: 'Dashboard', route: '/', group: 'Core', description: 'Landing dashboard and operational summary.', icon: <LayoutDashboard className="h-5 w-5" /> },
  { key: 'devices', label: 'Devices', route: '/devices', group: 'Core', description: 'Managed device list, details, and inventory entry points.', icon: <Server className="h-5 w-5" /> },
  { key: 'inventory', label: 'Inventory', route: '/inventory', group: 'Core', description: 'Hardware, software, module, interface, and lifecycle inventory.', icon: <Package className="h-5 w-5" /> },
  { key: 'credentials', label: 'Credentials', route: '/credentials', group: 'Core', description: 'Credential profiles and device access material.', icon: <KeyRound className="h-5 w-5" /> },
  { key: 'performance', label: 'Performance', route: '/performance', group: 'Operations', description: 'KPI charts, utilization, health, and historical performance.', icon: <Activity className="h-5 w-5" /> },
  { key: 'telemetry', label: 'Telemetry', route: '/telemetry', group: 'Operations', description: 'Streaming telemetry collectors, sensor paths, subscriptions, and samples.', icon: <RadioTower className="h-5 w-5" /> },
  { key: 'alarms', label: 'Alarms', route: '/alarms', group: 'Operations', description: 'Active alarms, history, rules, acknowledgement, and event workflows.', icon: <Bell className="h-5 w-5" /> },
  { key: 'assurance', label: 'Assurance', route: '/assurance', group: 'Operations', description: 'Assurance views for service and network health validation.', icon: <ShieldCheck className="h-5 w-5" /> },
  { key: 'services', label: 'Services', route: '/services', group: 'Operations', description: 'Service inventory, circuit context, and operational service views.', icon: <Waypoints className="h-5 w-5" /> },
  { key: 'ai_ops', label: 'AI Ops', route: '/ai-ops', group: 'Analytics', description: 'AI recommendations, incident summaries, and assistant workflows.', icon: <Bot className="h-5 w-5" /> },
  { key: 'monitoring_policies', label: 'Monitoring Policies', route: '/monitoring-policies', group: 'Automation', description: 'Monitoring templates, runs, and policy assignment.', icon: <ClipboardList className="h-5 w-5" /> },
  { key: 'topology', label: 'Topology', route: '/topology', group: 'Operations', description: 'Topology maps, circuits, VPNs, and network relationships.', icon: <Network className="h-5 w-5" /> },
  { key: 'discovery', label: 'Discovery', route: '/discovery', group: 'Automation', description: 'Network discovery jobs and onboarding workflows.', icon: <Radar className="h-5 w-5" /> },
  { key: 'commands', label: 'Commands', route: '/commands', group: 'Automation', description: 'Approved command execution, scheduling, and command history.', icon: <Terminal className="h-5 w-5" /> },
  { key: 'ios', label: 'IOS Versions', route: '/ios', group: 'Core', description: 'Software image and IOS version visibility.', icon: <Layers className="h-5 w-5" /> },
  { key: 'reports', label: 'Reports', route: '/reports', group: 'Analytics', description: 'Operational reports and export workflows.', icon: <FileText className="h-5 w-5" /> },
];

export const moduleByKey = Object.fromEntries(MODULES.map((module) => [module.key, module])) as Record<ModuleKey, ModuleMeta>;
