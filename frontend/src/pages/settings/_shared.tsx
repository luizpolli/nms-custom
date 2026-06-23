/**
 * Shared building blocks for Settings panels (P1.5 split of Settings.tsx).
 *
 * The Settings page used to live in a 2,452-line file. To make that
 * maintainable we kept every panel function 1:1 and just relocated them
 * into per-area modules. This module holds the cross-cutting helpers and
 * constants the panels depend on. Importing them from a single place
 * keeps the panels typo-resistant and lets us add coverage later without
 * chasing five copies of the same hook.
 *
 * Nothing here was redesigned — it's the same code, in a new home.
 */

import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Network,
  Bell,
  RadioTower,
  Users,
  ShieldCheck,
  ServerCog,
  BrainCircuit,
  FlaskConical,
  ToggleLeft,
  Wrench,
} from 'lucide-react';
import { Button } from '../../components/ui';
import { api } from '../../lib/api';

// ─── Top-level category model ────────────────────────────────────────────────

export type CategoryKey =
  | 'general'
  | 'system'
  | 'security'
  | 'usersRoles'
  | 'networkDevices'
  | 'inventory'
  | 'alarmsEvents'
  | 'eventForwarding'
  | 'modules'
  | 'integrationsAiOps'
  | 'labOperations'
  | 'systemAdmin';

export interface Category {
  key: CategoryKey;
  number: number;
  title: string;
  description: string;
  icon: React.ReactNode;
  submenus: string[];
  status?: 'live' | 'partial' | 'planned';
}

export const CATEGORY_PERMISSIONS: Record<CategoryKey, string[]> = {
  general: ['administrative_operations_system_settings'],
  system: ['administrative_operations_system_settings'],
  security: ['administrative_operations_system_settings'],
  usersRoles: ['administrative_operations_users_and_groups', 'user_administration_users_and_groups', 'administrative_operations_view_audit_logs_access', 'administrative_operations_audit_trails'],
  networkDevices: ['administrative_operations_system_settings', 'system_settings_submenu_network_and_device_snmp'],
  inventory: ['administrative_operations_system_settings', 'system_settings_submenu_inventory_inventory'],
  alarmsEvents: ['administrative_operations_system_settings', 'system_settings_submenu_alarm_and_events_alarm_and_events'],
  eventForwarding: ['administrative_operations_system_settings', 'nbi.write'],
  modules: ['administrative_operations_system_settings'],
  integrationsAiOps: ['administrative_operations_system_settings'],
  labOperations: ['administrative_operations_system_settings', 'system_settings_submenu_performance_ptp_synce'],
  systemAdmin: ['administrative_operations_system_settings'],
};

export const SUBMENU_PERMISSIONS: Partial<Record<CategoryKey, Record<string, string[]>>> = {
  general: {
    Appearance: ['administrative_operations_user_preferences'],
    'Polling summary': ['administrative_operations_system_settings'],
  },
  system: {
    'Server tuning': ['system_settings_submenu_general_server'],
    Database: ['administrative_operations_system_settings'],
    Jobs: ['system_settings_submenu_general_job_approval', 'job_management_view_job'],
    Backups: ['administrative_operations_system_settings'],
    'Software updates': ['system_settings_submenu_general_software_update'],
  },
  security: {
    'HTTPS / TLS': ['administrative_operations_system_settings'],
    Certificates: ['administrative_operations_system_settings'],
    'API auth': ['administrative_operations_system_settings'],
    Sessions: ['administrative_operations_system_settings'],
  },
  usersRoles: {
    Users: ['administrative_operations_users_and_groups', 'user_administration_users_and_groups'],
    Roles: ['administrative_operations_users_and_groups', 'user_administration_users_and_groups'],
    'Task permissions': ['administrative_operations_users_and_groups'],
    'Virtual domains': ['administrative_operations_virtual_domain_management', 'user_administration_virtual_domain_management'],
    'Account audit': ['administrative_operations_view_audit_logs_access', 'administrative_operations_audit_trails'],
    'CSV export': ['administrative_operations_view_audit_logs_access', 'administrative_operations_audit_trails'],
  },
  networkDevices: {
    'CLI session': ['administrative_operations_device_console_config'],
    'SNMP defaults': ['system_settings_submenu_network_and_device_snmp'],
    'MIB catalog': ['system_settings_submenu_network_and_device_snmp'],
    'Config archives': ['system_settings_submenu_inventory_configuration_archive'],
    'Image management': ['system_settings_submenu_inventory_software_image_management'],
    Discovery: ['system_settings_submenu_inventory_network_discovery'],
    'Device groups': ['groups_management_modify_groups'],
    Lifecycle: ['system_settings_submenu_inventory_inventory'],
    'Credentials policy': ['network_configuration_credential_profile_view_access'],
    'Plug & Play': ['network_configuration_auto_provisioning'],
    'Controller upgrades': ['software_image_management_swim_access_privilege'],
  },
  inventory: {
    'Config archives': ['system_settings_submenu_inventory_configuration_archive'],
    'Image management': ['system_settings_submenu_inventory_software_image_management'],
    Discovery: ['system_settings_submenu_inventory_network_discovery'],
    'Device groups': ['groups_management_modify_groups'],
    Lifecycle: ['system_settings_submenu_inventory_inventory'],
  },
  alarmsEvents: {
    'Alarm rules': ['system_settings_submenu_alarm_and_events_alarm_severity_and_auto_clear'],
    'Severity mapping': ['system_settings_submenu_alarm_and_events_alarm_severity_and_auto_clear'],
    'Trap storage': ['system_settings_submenu_alarm_and_events_alarm_and_events'],
    Syslog: ['system_settings_submenu_alarm_and_events_system_event_configuration'],
    'Event retention': ['system_settings_submenu_alarm_and_events_alarm_and_events'],
    Notifications: ['system_settings_submenu_alarm_and_events_alarm_notification_policies'],
  },
  eventForwarding: {
    'Mail notifications': ['system_settings_submenu_mail_notification_mail_server_configuration'],
    Targets: ['administrative_operations_system_settings', 'nbi.write'],
    Testing: ['administrative_operations_system_settings', 'nbi.write'],
    Filters: ['system_settings_submenu_alarm_and_events_alarm_and_events'],
  },
  modules: {
    'Module catalog': ['administrative_operations_system_settings'],
    'Customer deployment profile': ['administrative_operations_system_settings'],
    'Route visibility': ['administrative_operations_system_settings'],
  },
  integrationsAiOps: {
    'Northbound API': ['nbi.read', 'nbi.write'],
    Webhooks: ['administrative_operations_system_settings'],
    'AI Ops': ['administrative_operations_system_settings'],
    'LLM providers': ['administrative_operations_system_settings'],
    'Export targets': ['reports_report_launch_pad'],
  },
  labOperations: {
    'Lab health': ['administrative_operations_health_monitor_details'],
    'Traffic simulator': ['administrative_operations_system_settings'],
    Maintenance: ['administrative_operations_scheduled_tasks_and_data_collection'],
    Runbooks: ['administrative_operations_system_settings'],
    'PTP / SyncE': ['system_settings_submenu_performance_ptp_synce'],
  },
  systemAdmin: {
    'Container status': ['administrative_operations_system_settings'],
    'Backup jobs': ['administrative_operations_system_settings'],
  },
};

export const CATEGORIES: Category[] = [
  {
    key: 'general',
    number: 1,
    title: 'General',
    description: 'Global UI preferences, product identity, and runtime polling summary.',
    icon: <SettingsIcon className="h-5 w-5" />,
    submenus: ['Appearance', 'Polling summary'],
    status: 'live',
  },
  {
    key: 'system',
    number: 2,
    title: 'System',
    description: 'Server, database, scheduled jobs, retention, backups, software updates, and runtime tuning.',
    icon: <ServerCog className="h-5 w-5" />,
    submenus: ['Server tuning', 'Database', 'Jobs', 'Backups', 'Software updates'],
    status: 'live',
  },
  {
    key: 'security',
    number: 3,
    title: 'Security',
    description: 'HTTPS/TLS, API authentication, root login, session limits, and certificate settings.',
    icon: <ShieldCheck className="h-5 w-5" />,
    submenus: ['HTTPS / TLS', 'Certificates', 'API auth', 'Sessions'],
    status: 'live',
  },
  {
    key: 'usersRoles',
    number: 4,
    title: 'Access Control',
    description: 'Local Web GUI and NBI users, Cisco-style roles, task permissions, virtual domains, and account audit review.',
    icon: <Users className="h-5 w-5" />,
    submenus: ['Users', 'Roles', 'Task permissions', 'Virtual domains', 'Account audit', 'CSV export'],
    status: 'live',
  },
  {
    key: 'networkDevices',
    number: 5,
    title: 'Network Devices & Inventory',
    description: 'Device access defaults, CLI/SNMP behavior, MIB catalog, configuration archives, discovery, groups, lifecycle, and software images.',
    icon: <Network className="h-5 w-5" />,
    submenus: ['CLI session', 'SNMP defaults', 'MIB catalog', 'Config archives', 'Image management', 'Discovery', 'Device groups', 'Lifecycle', 'Credentials policy', 'Plug & Play', 'Controller upgrades'],
    status: 'live',
  },
  {
    key: 'alarmsEvents',
    number: 6,
    title: 'Alarms / Events',
    description: 'Alarm rules, severity mappings, trap/syslog intake, event retention, notification rules, and suppression defaults.',
    icon: <Bell className="h-5 w-5" />,
    submenus: ['Alarm rules', 'Severity mapping', 'Trap storage', 'Syslog', 'Event retention', 'Notifications'],
    status: 'live',
  },
  {
    key: 'eventForwarding',
    number: 7,
    title: 'Notifications & Forwarding',
    description: 'SMTP notification settings and northbound relay targets for traps, syslogs, telemetry events, generated alarms, and account audit events.',
    icon: <RadioTower className="h-5 w-5" />,
    submenus: ['Mail notifications', 'Targets', 'Testing', 'Filters'],
    status: 'live',
  },
  {
    key: 'modules',
    number: 8,
    title: 'Modules / Feature Control',
    description: 'Enable or disable operational modules per customer deployment, hiding unused pages and blocking direct route access.',
    icon: <ToggleLeft className="h-5 w-5" />,
    submenus: ['Module catalog', 'Customer deployment profile', 'Route visibility'],
    status: 'live',
  },
  {
    key: 'integrationsAiOps',
    number: 9,
    title: 'AI Ops',
    description: 'Enable or disable AI Ops recommendations, and review the active LLM provider configuration.',
    icon: <BrainCircuit className="h-5 w-5" />,
    submenus: ['AI Ops'],
    status: 'live',
  },
  {
    key: 'labOperations',
    number: 10,
    title: 'Lab / Operations',
    description: 'Certification readiness, lab health, traffic simulator hooks, maintenance windows, operational runbooks, and PTP/SyncE.',
    icon: <FlaskConical className="h-5 w-5" />,
    submenus: ['Lab health', 'Traffic simulator', 'Maintenance', 'Runbooks', 'PTP / SyncE'],
    status: 'live',
  },
  {
    key: 'systemAdmin',
    number: 11,
    title: 'System Administration',
    description: 'Container status and restart, scheduled backup jobs, backup history, and backup configuration.',
    icon: <Wrench className="h-5 w-5" />,
    submenus: ['Container status', 'Backup jobs'],
    status: 'live',
  },
];

export const SETTINGS_SECTION_INTRO_STORAGE_PREFIX = 'nms-settings-section-intro-v2';

// ─── Per-panel resource loader ───────────────────────────────────────────────

/**
 * Settings panels all follow the same load-show-save loop against a single
 * REST endpoint. This hook captures that pattern: GET on mount, PUT on save,
 * with loading/saving/saved/error state surfaced for the SaveBar.
 */
export function useSettingsResource<T>(endpoint: string, defaults: T) {
  const [cfg, setCfg] = useState<T>(defaults);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    api.get(endpoint)
      .then((r) => {
        if (mounted) setCfg(r.data);
      })
      .catch(() => {
        if (mounted) setError('Settings could not be loaded.');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [endpoint]);

  const save = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const r = await api.put(endpoint, cfg);
      setCfg(r.data);
      setSaved(true);
      return r.data as T;
    } catch {
      setError('Save failed. Check field values and try again.');
      return null;
    } finally {
      setSaving(false);
    }
  };

  return { cfg, setCfg, loading, saving, saved, error, save };
}

// ─── Save bar shared by every panel ──────────────────────────────────────────

export function SettingsSaveBar({
  label,
  loading,
  saving,
  saved,
  error,
  onSave,
}: {
  label: string;
  loading?: boolean;
  saving: boolean;
  saved: boolean;
  error: string | null;
  onSave: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={onSave} disabled={saving || loading}>{saving ? 'Saving...' : label}</Button>
      {loading && <span className="text-sm text-gray-500">Loading settings...</span>}
      {saved && <span className="text-sm text-green-600">Saved.</span>}
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  );
}

// ─── Generic inline hint used by panels ──────────────────────────────────────

export function SettingsHint({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
      {children}
    </div>
  );
}
