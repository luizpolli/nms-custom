import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Users,
  ChevronRight,
  Search,
  X,
  Lock,
  FileSearch,
  Download,
} from 'lucide-react';
import { useThemeStore, type Theme } from '../stores/theme';
import { useAuthStore } from '../stores/auth';
import { Card, CardHeader } from '../components/ui/Card';
import { PageHeader } from '../components/ui/PageHeader';
import { Select } from '../components/ui/Select';
import { Button, Input, Badge, PageIntroFloat } from '../components/ui';
import { api } from '../lib/api';
import { ForwardingSettings } from './settings/ForwardingSettings';
import { AlarmRulesPage } from './alarms/AlarmRulesPage';
import { MIBsPage } from './mibs/MIBsPage';
import { LabHealthPage } from './lab/LabHealthPage';
import { MODULES, MODULE_DEFAULTS, type ModuleControlSettings, type ModuleKey } from '../lib/moduleControls';
import { useModuleControls } from '../components/layout/ModuleControlProvider';
import {
  CATEGORIES,
  CATEGORY_PERMISSIONS,
  SUBMENU_PERMISSIONS,
  SETTINGS_SECTION_INTRO_STORAGE_PREFIX,
  SettingsHint,
  SettingsSaveBar,
  useSettingsResource,
  type Category,
  type CategoryKey,
} from './settings/_shared';
import { ClientsUsersPanel, type AppUser, type AppRole } from './settings/UsersRolesPanel';

// Account audit log type stays here because SettingsAuditPanel / AccountAuditPanel
// (defined later in this file) consume it. When those panels move out in a
// follow-up split, this can move too.
interface SettingsAuditLog {
  id: string;
  timestamp: string;
  actor?: string | null;
  action: string;
  object_id?: string | null;
  source_ip?: string | null;
  message?: string | null;
  outcome: string;
  details?: Record<string, unknown> | null;
}

interface GeneralAdminSettings {
  product_name: string;
  deployment_name: string;
  default_theme: Theme;
  support_contact_name: string;
  support_contact_email: string;
  tac_case_url: string;
  cisco_account_name: string;
}

const GENERAL_DEFAULTS: GeneralAdminSettings = {
  product_name: 'NMS Custom',
  deployment_name: 'Lab',
  default_theme: 'system',
  support_contact_name: '',
  support_contact_email: '',
  tac_case_url: '',
  cisco_account_name: '',
};

function GeneralPanel() {
  const { theme, setTheme } = useThemeStore();
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/general', GENERAL_DEFAULTS);
  const setGeneral = <K extends keyof GeneralAdminSettings>(k: K, v: GeneralAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Product Identity and Appearance" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">Product display name</span>
            <Input value={cfg.product_name} onChange={(e) => setGeneral('product_name', e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Deployment name</span>
            <Input value={cfg.deployment_name} onChange={(e) => setGeneral('deployment_name', e.target.value)} placeholder="Production, Lab, Certification" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Theme</span>
            <Select
              value={theme}
              onChange={(e) => {
                const next = e.target.value as Theme;
                setTheme(next);
                setGeneral('default_theme', next);
              }}
              className="max-w-xs"
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </Select>
          </label>
          <SettingsHint>
            The active browser theme applies immediately. The saved default records the deployment preference.
          </SettingsHint>
        </div>
      </Card>
      <Card>
        <CardHeader title="Runtime Polling Summary" />
        <dl className="grid grid-cols-1 gap-3 p-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-gray-500">KPI poll interval</dt>
            <dd>60s (backend env: <code>POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Topology poll interval</dt>
            <dd>300s (<code>TOPOLOGY_POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Alarm poll interval</dt>
            <dd>30s (<code>ALARM_POLL_INTERVAL</code>)</dd>
          </div>
          <div>
            <dt className="text-gray-500">Polling workers</dt>
            <dd>4 (<code>POLL_WORKERS</code>)</dd>
          </div>
        </dl>
      </Card>
      <SettingsSaveBar label="Save General Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
    </div>
  );
}


// ---------------------------------------------------------------------------
// System panel: mail / jobs / retention
// ---------------------------------------------------------------------------

interface SystemMailCfg { smtp_host: string; smtp_port: number; smtp_from: string; smtp_use_tls: boolean; smtp_username: string; }
interface SystemJobsCfg { job_concurrency: number; job_retry_backoff_seconds: number; job_max_retries: number; }
interface SystemRetentionCfg { alarm_retention_days: number; event_retention_days: number; kpi_retention_days: number; telemetry_sample_retention_days: number; }
interface SystemAdminSettings { mail: SystemMailCfg; jobs: SystemJobsCfg; retention: SystemRetentionCfg; }

const SYSTEM_DEFAULTS: SystemAdminSettings = {
  mail: { smtp_host: '', smtp_port: 587, smtp_from: '', smtp_use_tls: true, smtp_username: '' },
  jobs: { job_concurrency: 4, job_retry_backoff_seconds: 30, job_max_retries: 3 },
  retention: { alarm_retention_days: 90, event_retention_days: 30, kpi_retention_days: 365, telemetry_sample_retention_days: 7 },
};

function SystemPanel() {
  const [cfg, setCfg] = useState<SystemAdminSettings>(SYSTEM_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/system').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setJobs = <K extends keyof SystemJobsCfg>(k: K, v: SystemJobsCfg[K]) =>
    setCfg((p) => ({ ...p, jobs: { ...p.jobs, [k]: v } }));
  const setRetention = <K extends keyof SystemRetentionCfg>(k: K, v: SystemRetentionCfg[K]) =>
    setCfg((p) => ({ ...p, retention: { ...p.retention, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/system', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Scheduled Jobs" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block font-medium">Job concurrency</span>
            <Input type="number" value={cfg.jobs.job_concurrency} onChange={(e) => setJobs('job_concurrency', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Retry backoff (seconds)</span>
            <Input type="number" value={cfg.jobs.job_retry_backoff_seconds} onChange={(e) => setJobs('job_retry_backoff_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Max retries</span>
            <Input type="number" value={cfg.jobs.job_max_retries} onChange={(e) => setJobs('job_max_retries', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Data Retention Windows" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          {([
            ['alarm_retention_days', 'Alarm retention (days)'],
            ['event_retention_days', 'Event retention (days)'],
            ['kpi_retention_days', 'KPI retention (days)'],
            ['telemetry_sample_retention_days', 'Telemetry sample retention (days)'],
          ] as [keyof SystemRetentionCfg, string][]).map(([key, label]) => (
            <label key={key} className="block">
              <span className="mb-1 block font-medium">{label}</span>
              <Input type="number" value={cfg.retention[key]} onChange={(e) => setRetention(key, Number(e.target.value))} />
            </label>
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save System Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

function MailNotificationPanel() {
  const [cfg, setCfg] = useState<SystemAdminSettings>(SYSTEM_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; checks: string[] } | null>(null);

  useEffect(() => {
    api.get('/settings/system').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setMail = <K extends keyof SystemMailCfg>(k: K, v: SystemMailCfg[K]) =>
    setCfg((p) => ({ ...p, mail: { ...p.mail, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/system', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  const testMail = async () => {
    setTesting(true); setTestResult(null); setError(null);
    try {
      const r = await api.post('/settings/mail/test', cfg.mail);
      setTestResult(r.data);
    } catch { setError('Mail test failed — check SMTP field values.'); }
    finally { setTesting(false); }
  };

  return (
    <Card>
      <CardHeader title="Mail Notifications (SMTP)" />
      <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
        <label className="block">
          <span className="mb-1 block font-medium">SMTP host</span>
          <Input value={cfg.mail.smtp_host} onChange={(e) => setMail('smtp_host', e.target.value)} placeholder="smtp.example.com" />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">SMTP port</span>
          <Input type="number" value={cfg.mail.smtp_port} onChange={(e) => setMail('smtp_port', Number(e.target.value))} />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">From address</span>
          <Input type="email" value={cfg.mail.smtp_from} onChange={(e) => setMail('smtp_from', e.target.value)} placeholder="nms@example.com" />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Username</span>
          <Input value={cfg.mail.smtp_username} onChange={(e) => setMail('smtp_username', e.target.value)} placeholder="optional" />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.mail.smtp_use_tls} onChange={(e) => setMail('smtp_use_tls', e.target.checked)} />
          Use TLS / STARTTLS
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-gray-200 p-4 dark:border-gray-700">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Mail Notification Settings'}</Button>
        <Button variant="outline" onClick={testMail} disabled={testing}>{testing ? 'Testing...' : 'Test Mail Notification'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
      {testResult && (
        <div className="space-y-2 border-t border-gray-200 p-4 text-sm dark:border-gray-700">
          <Badge variant={testResult.ok ? 'success' : 'danger'}>{testResult.ok ? 'Passed' : 'Failed'}</Badge>
          <p className="text-gray-700 dark:text-gray-200">{testResult.message}</p>
          <ul className="list-disc space-y-1 pl-5 text-xs text-gray-500 dark:text-gray-400">
            {testResult.checks.map((check) => <li key={check}>{check}</li>)}
          </ul>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Network Devices panel: CLI / SNMP defaults
// ---------------------------------------------------------------------------

interface NetworkCliCfg { ssh_timeout_seconds: number; ssh_port: number; cli_retries: number; max_concurrent_ssh_sessions: number; terminal_length: number; }
interface NetworkSnmpCfg { snmp_version: 'v2c' | 'v3'; snmp_community: string; snmp_port: number; snmp_timeout_seconds: number; snmp_retries: number; polling_interval_seconds: number; }
interface NetworkDeviceAdminSettings { cli: NetworkCliCfg; snmp: NetworkSnmpCfg; }

const NETWORK_DEFAULTS: NetworkDeviceAdminSettings = {
  cli: { ssh_timeout_seconds: 30, ssh_port: 22, cli_retries: 2, max_concurrent_ssh_sessions: 10, terminal_length: 0 },
  snmp: { snmp_version: 'v2c', snmp_community: 'public', snmp_port: 161, snmp_timeout_seconds: 5, snmp_retries: 2, polling_interval_seconds: 60 },
};

function NetworkDevicesPanel() {
  const [cfg, setCfg] = useState<NetworkDeviceAdminSettings>(NETWORK_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/network-devices').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setCli = <K extends keyof NetworkCliCfg>(k: K, v: NetworkCliCfg[K]) =>
    setCfg((p) => ({ ...p, cli: { ...p.cli, [k]: v } }));
  const setSnmp = <K extends keyof NetworkSnmpCfg>(k: K, v: NetworkSnmpCfg[K]) =>
    setCfg((p) => ({ ...p, snmp: { ...p.snmp, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/network-devices', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="CLI Session Defaults" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">SSH timeout (seconds)</span>
            <Input type="number" value={cfg.cli.ssh_timeout_seconds} onChange={(e) => setCli('ssh_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">SSH port</span>
            <Input type="number" value={cfg.cli.ssh_port} onChange={(e) => setCli('ssh_port', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">CLI retries</span>
            <Input type="number" value={cfg.cli.cli_retries} onChange={(e) => setCli('cli_retries', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Max concurrent SSH sessions</span>
            <Input type="number" value={cfg.cli.max_concurrent_ssh_sessions} onChange={(e) => setCli('max_concurrent_ssh_sessions', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Terminal length (0 = no-more-prompt)</span>
            <Input type="number" value={cfg.cli.terminal_length} onChange={(e) => setCli('terminal_length', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="SNMP Defaults" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">SNMP version</span>
            <Select value={cfg.snmp.snmp_version} onChange={(e) => setSnmp('snmp_version', e.target.value as 'v2c' | 'v3')} className="max-w-xs">
              <option value="v2c">v2c</option>
              <option value="v3">v3</option>
            </Select>
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Community string</span>
            <Input value={cfg.snmp.snmp_community} onChange={(e) => setSnmp('snmp_community', e.target.value)} placeholder="public" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">SNMP port</span>
            <Input type="number" value={cfg.snmp.snmp_port} onChange={(e) => setSnmp('snmp_port', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Timeout (seconds)</span>
            <Input type="number" value={cfg.snmp.snmp_timeout_seconds} onChange={(e) => setSnmp('snmp_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Retries</span>
            <Input type="number" value={cfg.snmp.snmp_retries} onChange={(e) => setSnmp('snmp_retries', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Polling interval (seconds)</span>
            <Input type="number" value={cfg.snmp.polling_interval_seconds} onChange={(e) => setSnmp('polling_interval_seconds', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <MIBsPage embedded />

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Network Device Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alarms/Events panel: severity / notifications / suppression
// ---------------------------------------------------------------------------

interface AlarmSeverityMapping { critical_oid_value: number; major_oid_value: number; minor_oid_value: number; warning_oid_value: number; info_oid_value: number; }
interface AlarmNotificationCfg { email_enabled: boolean; email_recipients: string; syslog_forward_enabled: boolean; syslog_forward_host: string; syslog_forward_port: number; min_severity_to_notify: string; }
interface AlarmSuppressionCfg { suppression_window_minutes: number; flap_detection_enabled: boolean; flap_threshold_count: number; }
interface AlarmsEventsAdminSettings { severity_mapping: AlarmSeverityMapping; notifications: AlarmNotificationCfg; suppression: AlarmSuppressionCfg; }

const ALARMS_DEFAULTS: AlarmsEventsAdminSettings = {
  severity_mapping: { critical_oid_value: 1, major_oid_value: 2, minor_oid_value: 3, warning_oid_value: 4, info_oid_value: 5 },
  notifications: { email_enabled: false, email_recipients: '', syslog_forward_enabled: false, syslog_forward_host: '', syslog_forward_port: 514, min_severity_to_notify: 'major' },
  suppression: { suppression_window_minutes: 5, flap_detection_enabled: true, flap_threshold_count: 3 },
};

function AlarmsEventsPanel() {
  const [cfg, setCfg] = useState<AlarmsEventsAdminSettings>(ALARMS_DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get('/settings/alarms-events').then((r) => setCfg(r.data)).catch(() => {});
  }, []);

  const setSev = <K extends keyof AlarmSeverityMapping>(k: K, v: number) =>
    setCfg((p) => ({ ...p, severity_mapping: { ...p.severity_mapping, [k]: v } }));
  const setNotif = <K extends keyof AlarmNotificationCfg>(k: K, v: AlarmNotificationCfg[K]) =>
    setCfg((p) => ({ ...p, notifications: { ...p.notifications, [k]: v } }));
  const setSuppr = <K extends keyof AlarmSuppressionCfg>(k: K, v: AlarmSuppressionCfg[K]) =>
    setCfg((p) => ({ ...p, suppression: { ...p.suppression, [k]: v } }));

  const save = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const r = await api.put('/settings/alarms-events', cfg);
      setCfg(r.data); setSaved(true);
    } catch { setError('Save failed — check field values.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="space-y-6">
      <AlarmRulesPage embedded />

      <Card>
        <CardHeader title="Severity OID Value Mapping" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          {([
            ['critical_oid_value', 'Critical'],
            ['major_oid_value', 'Major'],
            ['minor_oid_value', 'Minor'],
            ['warning_oid_value', 'Warning'],
            ['info_oid_value', 'Info'],
          ] as [keyof AlarmSeverityMapping, string][]).map(([key, label]) => (
            <label key={key} className="block">
              <span className="mb-1 block font-medium">{label} OID value</span>
              <Input type="number" value={cfg.severity_mapping[key]} onChange={(e) => setSev(key, Number(e.target.value))} />
            </label>
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="Notification Channels" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="flex items-center gap-2 md:col-span-2">
            <input type="checkbox" checked={cfg.notifications.email_enabled} onChange={(e) => setNotif('email_enabled', e.target.checked)} />
            Enable email notifications
          </label>
          <label className="block md:col-span-2">
            <span className="mb-1 block font-medium">Email recipients (comma-separated)</span>
            <Input value={cfg.notifications.email_recipients} onChange={(e) => setNotif('email_recipients', e.target.value)} placeholder="noc@corp.com, admin@corp.com" disabled={!cfg.notifications.email_enabled} />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={cfg.notifications.syslog_forward_enabled} onChange={(e) => setNotif('syslog_forward_enabled', e.target.checked)} />
            Forward to syslog server
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Syslog host</span>
            <Input value={cfg.notifications.syslog_forward_host} onChange={(e) => setNotif('syslog_forward_host', e.target.value)} placeholder="syslog.corp.com" disabled={!cfg.notifications.syslog_forward_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Syslog port</span>
            <Input type="number" value={cfg.notifications.syslog_forward_port} onChange={(e) => setNotif('syslog_forward_port', Number(e.target.value))} disabled={!cfg.notifications.syslog_forward_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Minimum severity to notify</span>
            <Select value={cfg.notifications.min_severity_to_notify} onChange={(e) => setNotif('min_severity_to_notify', e.target.value)} className="max-w-xs">
              <option value="critical">Critical</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </Select>
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Suppression and Flap Detection" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="block">
            <span className="mb-1 block font-medium">Suppression window (minutes)</span>
            <Input type="number" value={cfg.suppression.suppression_window_minutes} onChange={(e) => setSuppr('suppression_window_minutes', Number(e.target.value))} />
          </label>
          <label className="flex items-center gap-2 md:pt-6">
            <input type="checkbox" checked={cfg.suppression.flap_detection_enabled} onChange={(e) => setSuppr('flap_detection_enabled', e.target.checked)} />
            Enable flap detection
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Flap threshold (count)</span>
            <Input type="number" value={cfg.suppression.flap_threshold_count} onChange={(e) => setSuppr('flap_threshold_count', Number(e.target.value))} disabled={!cfg.suppression.flap_detection_enabled} />
          </label>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Alarms & Events Settings'}</Button>
        {saved && <span className="text-sm text-green-600">Saved.</span>}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  );
}

function SettingsAuditPanel() {
  const [entries, setEntries] = useState<SettingsAuditLog[]>([]);

  useEffect(() => {
    api.get('/settings/audit?limit=8').then((r) => setEntries(r.data)).catch(() => setEntries([]));
  }, []);

  return (
    <Card>
      <CardHeader title="Recent Settings Audit" />
      <div className="overflow-x-auto p-4">
        <table className="min-w-full text-sm">
          <thead className="text-xs uppercase text-gray-500">
            <tr>
              <th className="px-3 py-2 text-left">Time</th>
              <th className="px-3 py-2 text-left">Action</th>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Actor</th>
              <th className="px-3 py-2 text-left">Outcome</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td className="px-3 py-2 text-gray-500">{new Date(entry.timestamp).toLocaleString()}</td>
                <td className="px-3 py-2 font-medium">{entry.action}</td>
                <td className="px-3 py-2">{entry.object_id || '-'}</td>
                <td className="px-3 py-2">{entry.actor || 'system'}</td>
                <td className="px-3 py-2"><Badge variant={entry.outcome === 'success' ? 'success' : 'warning'}>{entry.outcome}</Badge></td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr><td className="px-3 py-4 text-gray-500" colSpan={5}>No settings audit events recorded yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AccountAuditPanel() {
  const [entries, setEntries] = useState<SettingsAuditLog[]>([]);
  const [filters, setFilters] = useState({ q: '', actor: '', action: '', role: '', outcome: '', since: '', until: '' });
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  const queryParams = () => {
    const params = new URLSearchParams({ limit: '100' });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return params;
  };

  const loadAudit = async () => {
    setLoading(true);
    try {
      const response = await api.get(`/settings/account-audit?${queryParams().toString()}`);
      setEntries(response.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAudit();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setFilter = (key: keyof typeof filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const params = queryParams();
      params.set('format', 'csv');
      params.delete('limit');
      const response = await api.get(`/settings/account-audit/export?${params.toString()}`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'account_audit_export.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const detailText = (entry: SettingsAuditLog, key: string) => {
    const value = entry.details?.[key];
    return typeof value === 'string' || typeof value === 'number' ? String(value) : '-';
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Account Activity" />
        <div className="space-y-4 p-4">
          <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-4">
            <Input placeholder="Search actor, action, path..." value={filters.q} onChange={(e) => setFilter('q', e.target.value)} />
            <Input placeholder="Actor" value={filters.actor} onChange={(e) => setFilter('actor', e.target.value)} />
            <Input placeholder="Action" value={filters.action} onChange={(e) => setFilter('action', e.target.value)} />
            <Select value={filters.role} onChange={(e) => setFilter('role', e.target.value)}>
              <option value="">Any role</option>
              <option value="root">Root</option>
              <option value="admin">Admin</option>
              <option value="operator">Operator</option>
              <option value="viewer">Viewer</option>
              <option value="ai-ops">AI Ops</option>
            </Select>
            <Select value={filters.outcome} onChange={(e) => setFilter('outcome', e.target.value)}>
              <option value="">Any outcome</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
            </Select>
            <Input type="datetime-local" value={filters.since} onChange={(e) => setFilter('since', e.target.value)} />
            <Input type="datetime-local" value={filters.until} onChange={(e) => setFilter('until', e.target.value)} />
            <div className="flex gap-2">
              <Button variant="secondary" onClick={loadAudit} loading={loading}>Apply</Button>
              <Button variant="outline" onClick={exportCsv} loading={exporting} leftIcon={<Download className="h-4 w-4" />}>Export</Button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-800">
                <tr>
                  {['Time', 'Actor', 'Role', 'Action', 'Outcome', 'Source IP', 'Path'].map((header) => (
                    <th key={header} className="px-3 py-2 text-left">{header}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td className="px-3 py-2 text-gray-500">{new Date(entry.timestamp).toLocaleString()}</td>
                    <td className="px-3 py-2 font-medium">{entry.actor || '-'}</td>
                    <td className="px-3 py-2">{detailText(entry, 'role')}</td>
                    <td className="px-3 py-2">{entry.action}</td>
                    <td className="px-3 py-2"><Badge variant={entry.outcome === 'success' ? 'success' : 'danger'}>{entry.outcome}</Badge></td>
                    <td className="px-3 py-2">{entry.source_ip || '-'}</td>
                    <td className="px-3 py-2">{detailText(entry, 'path')}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr><td className="px-3 py-4 text-gray-500" colSpan={7}>No account audit events match the current filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Card>
    </div>
  );
}

interface InventoryAdminSettings {
  config_archive_enabled: boolean;
  config_archive_frequency_minutes: number;
  config_archive_retention_days: number;
  image_repository_path: string;
  default_discovery_profile: string;
  auto_group_by_site: boolean;
  lifecycle_warning_days: number;
}

const INVENTORY_DEFAULTS: InventoryAdminSettings = {
  config_archive_enabled: true,
  config_archive_frequency_minutes: 1440,
  config_archive_retention_days: 90,
  image_repository_path: '',
  default_discovery_profile: 'snmp-cli',
  auto_group_by_site: true,
  lifecycle_warning_days: 180,
};

function InventorySettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/inventory', INVENTORY_DEFAULTS);
  const setInventory = <K extends keyof InventoryAdminSettings>(k: K, v: InventoryAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Configuration Archives" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="flex items-center gap-2 md:col-span-3">
            <input type="checkbox" checked={cfg.config_archive_enabled} onChange={(e) => setInventory('config_archive_enabled', e.target.checked)} />
            Enable scheduled configuration archives
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Archive frequency (minutes)</span>
            <Input type="number" value={cfg.config_archive_frequency_minutes} onChange={(e) => setInventory('config_archive_frequency_minutes', Number(e.target.value))} disabled={!cfg.config_archive_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Archive retention (days)</span>
            <Input type="number" value={cfg.config_archive_retention_days} onChange={(e) => setInventory('config_archive_retention_days', Number(e.target.value))} disabled={!cfg.config_archive_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Lifecycle warning (days)</span>
            <Input type="number" value={cfg.lifecycle_warning_days} onChange={(e) => setInventory('lifecycle_warning_days', Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Image Management and Discovery Defaults" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">Image repository path</span>
            <Input value={cfg.image_repository_path} onChange={(e) => setInventory('image_repository_path', e.target.value)} placeholder="/var/lib/nms/images" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Default discovery profile</span>
            <Input value={cfg.default_discovery_profile} onChange={(e) => setInventory('default_discovery_profile', e.target.value)} placeholder="snmp-cli" />
          </label>
          <label className="flex items-center gap-2 md:col-span-2">
            <input type="checkbox" checked={cfg.auto_group_by_site} onChange={(e) => setInventory('auto_group_by_site', e.target.checked)} />
            Automatically group discovered devices by site metadata when available
          </label>
        </div>
      </Card>

      <SettingsSaveBar label="Save Inventory Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
    </div>
  );
}

function ModuleControlSettingsPanel() {
  const moduleControls = useModuleControls();
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/modules', MODULE_DEFAULTS);
  const disabledCount = Object.values(cfg).filter((enabled) => !enabled).length;
  const groups = Array.from(new Set(MODULES.map((module) => module.group)));

  const setModule = (key: ModuleKey, enabled: boolean) => {
    setCfg((prev) => ({ ...prev, [key]: enabled }));
  };

  const setAll = (enabled: boolean) => {
    setCfg(MODULES.reduce((acc, module) => ({ ...acc, [module.key]: enabled }), {} as ModuleControlSettings));
  };

  const saveModules = async () => {
    const savedModules = await save();
    if (savedModules) {
      window.dispatchEvent(new CustomEvent('nms-modules-updated', { detail: savedModules }));
      await moduleControls.refresh();
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Customer Module Catalog" />
        <div className="space-y-4 p-4 text-sm">
          <SettingsHint>
            Disable modules a customer does not use. Disabled modules are removed from the sidebar and direct URL access shows a disabled-module screen. Settings remains always available so admins can re-enable modules.
          </SettingsHint>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
            <div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">Deployment profile</div>
              <div className="text-xs text-gray-500">
                {MODULES.length - disabledCount} enabled, {disabledCount} disabled
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setAll(true)}>Enable all</Button>
              <Button variant="outline" size="sm" onClick={() => setAll(false)}>Disable all operational modules</Button>
            </div>
          </div>

          {groups.map((group) => (
            <div key={group} className="rounded-lg border border-gray-200 dark:border-gray-700">
              <div className="border-b border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold uppercase text-gray-500 dark:border-gray-700 dark:bg-gray-800">
                {group}
              </div>
              <div className="divide-y divide-gray-100 dark:divide-gray-800">
                {MODULES.filter((module) => module.group === group).map((module) => {
                  const enabled = cfg[module.key] !== false;
                  return (
                    <div key={module.key} className="flex flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex min-w-0 items-start gap-3">
                        <span className={`mt-0.5 ${enabled ? 'text-cisco-blue' : 'text-gray-400'}`}>{module.icon}</span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-gray-900 dark:text-gray-100">{module.label}</span>
                            <Badge variant={enabled ? 'success' : 'neutral'}>{enabled ? 'Enabled' : 'Disabled'}</Badge>
                            <span className="text-xs text-gray-400">{module.route}</span>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{module.description}</p>
                        </div>
                      </div>
                      <label className="inline-flex shrink-0 items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={(event) => setModule(module.key, event.target.checked)}
                        />
                        <span>{enabled ? 'On' : 'Off'}</span>
                      </label>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <SettingsSaveBar label="Save Module Controls" loading={loading} saving={saving || moduleControls.loading} saved={saved} error={error} onSave={saveModules} />
    </div>
  );
}

interface IntegrationsAiOpsAdminSettings {
  nbi_enabled: boolean;
  webhook_retry_attempts: number;
  webhook_timeout_seconds: number;
  ai_ops_enabled: boolean;
  ai_recommendation_min_confidence: number;
  llm_provider: 'local' | 'openai' | 'azure' | 'custom';
  llm_model: string;
  report_export_target_path: string;
}

const INTEGRATIONS_DEFAULTS: IntegrationsAiOpsAdminSettings = {
  nbi_enabled: true,
  webhook_retry_attempts: 3,
  webhook_timeout_seconds: 10,
  ai_ops_enabled: true,
  ai_recommendation_min_confidence: 70,
  llm_provider: 'local',
  llm_model: '',
  report_export_target_path: '',
};

function IntegrationsAiOpsSettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/integrations-ai-ops', INTEGRATIONS_DEFAULTS);
  const setIntegration = <K extends keyof IntegrationsAiOpsAdminSettings>(k: K, v: IntegrationsAiOpsAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Northbound API and Webhooks" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="flex items-center gap-2 md:col-span-3">
            <input type="checkbox" checked={cfg.nbi_enabled} onChange={(e) => setIntegration('nbi_enabled', e.target.checked)} />
            Enable northbound API access
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Webhook retries</span>
            <Input type="number" value={cfg.webhook_retry_attempts} onChange={(e) => setIntegration('webhook_retry_attempts', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Webhook timeout (seconds)</span>
            <Input type="number" value={cfg.webhook_timeout_seconds} onChange={(e) => setIntegration('webhook_timeout_seconds', Number(e.target.value))} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Report export target path</span>
            <Input value={cfg.report_export_target_path} onChange={(e) => setIntegration('report_export_target_path', e.target.value)} placeholder="/exports/reports" />
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="AI Ops and LLM Provider" />
        <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-3">
          <label className="flex items-center gap-2 md:col-span-3">
            <input type="checkbox" checked={cfg.ai_ops_enabled} onChange={(e) => setIntegration('ai_ops_enabled', e.target.checked)} />
            Enable AI Ops recommendations
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Minimum confidence (%)</span>
            <Input type="number" value={cfg.ai_recommendation_min_confidence} onChange={(e) => setIntegration('ai_recommendation_min_confidence', Number(e.target.value))} disabled={!cfg.ai_ops_enabled} />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">LLM provider</span>
            <Select value={cfg.llm_provider} onChange={(e) => setIntegration('llm_provider', e.target.value as IntegrationsAiOpsAdminSettings['llm_provider'])} disabled={!cfg.ai_ops_enabled}>
              <option value="local">Local</option>
              <option value="openai">OpenAI</option>
              <option value="azure">Azure OpenAI</option>
              <option value="custom">Custom</option>
            </Select>
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Model name</span>
            <Input value={cfg.llm_model} onChange={(e) => setIntegration('llm_model', e.target.value)} placeholder="optional" disabled={!cfg.ai_ops_enabled} />
          </label>
          <div className="md:col-span-3">
            <SettingsHint>API keys and tokens should stay in environment variables or secret stores. This screen saves provider references and behavior knobs only.</SettingsHint>
          </div>
        </div>
      </Card>

      <SettingsSaveBar label="Save Integrations / AI Ops Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
    </div>
  );
}

interface LabOperationsAdminSettings {
  certification_mode_enabled: boolean;
  traffic_simulator_enabled: boolean;
  simulator_profile: string;
  maintenance_mode_enabled: boolean;
  maintenance_window: string;
  runbook_url: string;
  ptp_synce_enabled: boolean;
}

const LAB_OPERATIONS_DEFAULTS: LabOperationsAdminSettings = {
  certification_mode_enabled: true,
  traffic_simulator_enabled: false,
  simulator_profile: 'baseline',
  maintenance_mode_enabled: false,
  maintenance_window: '',
  runbook_url: '',
  ptp_synce_enabled: false,
};

function LabOperationsSettingsPanel() {
  const { cfg, setCfg, loading, saving, saved, error, save } = useSettingsResource('/settings/lab-operations', LAB_OPERATIONS_DEFAULTS);
  const setLab = <K extends keyof LabOperationsAdminSettings>(k: K, v: LabOperationsAdminSettings[K]) =>
    setCfg((p) => ({ ...p, [k]: v }));

  return (
    <Card>
      <CardHeader title="Certification and Operations Controls" />
      <div className="grid grid-cols-1 gap-4 p-4 text-sm md:grid-cols-2">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.certification_mode_enabled} onChange={(e) => setLab('certification_mode_enabled', e.target.checked)} />
          Certification readiness mode
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.ptp_synce_enabled} onChange={(e) => setLab('ptp_synce_enabled', e.target.checked)} />
          Enable PTP / SyncE validation checks
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.traffic_simulator_enabled} onChange={(e) => setLab('traffic_simulator_enabled', e.target.checked)} />
          Traffic simulator hooks
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Simulator profile</span>
          <Input value={cfg.simulator_profile} onChange={(e) => setLab('simulator_profile', e.target.value)} disabled={!cfg.traffic_simulator_enabled} />
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={cfg.maintenance_mode_enabled} onChange={(e) => setLab('maintenance_mode_enabled', e.target.checked)} />
          Maintenance mode
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">Maintenance window</span>
          <Input value={cfg.maintenance_window} onChange={(e) => setLab('maintenance_window', e.target.value)} placeholder="Sunday 01:00-03:00" disabled={!cfg.maintenance_mode_enabled} />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-1 block font-medium">Runbook URL</span>
          <Input value={cfg.runbook_url} onChange={(e) => setLab('runbook_url', e.target.value)} placeholder="https://..." />
        </label>
        <div className="md:col-span-2">
          <SettingsSaveBar label="Save Lab / Operations Settings" loading={loading} saving={saving} saved={saved} error={error} onSave={save} />
        </div>
      </div>
    </Card>
  );
}

function AccessControlPanel() {
  type AccessControlTab = 'usersRoles' | 'accountAudit';
  const [tab, setTab] = useState<AccessControlTab>('usersRoles');
  const tabs: Array<{ key: AccessControlTab; label: string; icon: React.ReactNode }> = [
    { key: 'usersRoles', label: 'Users & Roles', icon: <Users className="h-4 w-4" /> },
    { key: 'accountAudit', label: 'Account Audit', icon: <FileSearch className="h-4 w-4" /> },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap gap-2 p-3">
          {tabs.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
                tab === item.key
                  ? 'border-cisco-blue bg-cisco-blue text-white'
                  : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      </Card>
      {tab === 'usersRoles' ? <ClientsUsersPanel mode="users" /> : <AccountAuditPanel />}
    </div>
  );
}

function NotificationsForwardingPanel() {
  return (
    <div className="space-y-6">
      <MailNotificationPanel />
      <ForwardingSettings />
    </div>
  );
}

function CategoryContent({ category }: { category: CategoryKey }) {
  switch (category) {
    case 'general':
      return <GeneralPanel />;
    case 'system':
      return (
        <div className="space-y-6">
          <SystemPanel />
          <SettingsAuditPanel />
        </div>
      );
    case 'security':
      return <ClientsUsersPanel mode="security" />;
    case 'usersRoles':
      return <AccessControlPanel />;
    case 'networkDevices':
      return (
        <div className="space-y-6">
          <NetworkDevicesPanel />
          <InventorySettingsPanel />
        </div>
      );
    case 'inventory':
      return (
        <div className="space-y-6">
          <NetworkDevicesPanel />
          <InventorySettingsPanel />
        </div>
      );
    case 'alarmsEvents':
      return <AlarmsEventsPanel />;
    case 'eventForwarding':
      return <NotificationsForwardingPanel />;
    case 'modules':
      return <ModuleControlSettingsPanel />;
    case 'integrationsAiOps':
      return <IntegrationsAiOpsSettingsPanel />;
    case 'labOperations':
      return (
        <div className="space-y-6">
          <LabHealthPage embedded />
          <LabOperationsSettingsPanel />
        </div>
      );
  }
}

const SECTION_KEYS = new Set<CategoryKey>([
  'general', 'system', 'security', 'usersRoles', 'networkDevices',
  'inventory', 'alarmsEvents', 'eventForwarding', 'modules', 'integrationsAiOps', 'labOperations',
]);

function isValidSection(s: string | null): s is CategoryKey {
  return s !== null && SECTION_KEYS.has(s as CategoryKey);
}

function normalizeSection(s: string | null): CategoryKey {
  if (s === 'inventory') return 'networkDevices';
  return isValidSection(s) ? s : 'general';
}

function settingsSearchText(category: Category): string {
  return [
    category.title,
    category.description,
    category.status || '',
    ...category.submenus,
  ].join(' ').toLowerCase();
}

function SettingsSectionDiagram({ category, submenus }: { category: Category; submenus: string[] }) {
  const primary = submenus.slice(0, 4);
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
      <div className="grid gap-3 lg:grid-cols-[1fr_auto_1.3fr_auto_1fr] lg:items-center">
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
            <span className="text-cisco-blue">{category.icon}</span>
            <span>{category.title}</span>
          </div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{category.description}</p>
        </div>
        <div className="hidden text-center text-xl text-gray-400 lg:block">-&gt;</div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Choose a function</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {primary.map((submenu) => (
              <span key={submenu} className="rounded bg-cisco-blue/10 px-2 py-1 text-xs text-cisco-blue dark:bg-cisco-blue/20">
                {submenu}
              </span>
            ))}
            {submenus.length > primary.length && (
              <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-500 dark:bg-gray-800">+{submenus.length - primary.length}</span>
            )}
          </div>
        </div>
        <div className="hidden text-center text-xl text-gray-400 lg:block">-&gt;</div>
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Apply and validate</div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Update settings, save when available, then validate the related operational page.
          </p>
        </div>
      </div>
    </div>
  );
}

function SettingsSectionIntro({ category, submenus, onDismiss }: { category: Category; submenus: string[]; onDismiss: (options: { dontShowAgain: boolean }) => void }) {
  return (
    <PageIntroFloat title={`${category.title} guide`} icon={category.icon} onDismiss={onDismiss}>
      <p className="mb-3 text-gray-600 dark:text-gray-300">{category.description}</p>
      <SettingsSectionDiagram category={category} submenus={submenus} />
    </PageIntroFloat>
  );
}

function Settings() {
  const authUser = useAuthStore((state) => state.user);
  const [searchParams, setSearchParams] = useSearchParams();
  const sectionParam = searchParams.get('section');
  const [settingsSearch, setSettingsSearch] = useState('');
  const [navUsers, setNavUsers] = useState<AppUser[]>([]);
  const [navRoles, setNavRoles] = useState<AppRole[]>([]);
  const [active, setActive] = useState<CategoryKey>(
    normalizeSection(sectionParam),
  );
  const [showSectionIntro, setShowSectionIntro] = useState(false);
  const normalizedSearch = settingsSearch.trim().toLowerCase();

  useEffect(() => {
    void Promise.all([
      api.get('/settings/users').then((r) => setNavUsers(r.data)).catch(() => setNavUsers([])),
      api.get('/settings/roles').then((r) => setNavRoles(r.data)).catch(() => setNavRoles([])),
    ]);
  }, []);

  const roleByName = new Map(navRoles.map((role) => [role.name, role]));
  const currentUser = navUsers.find((user) => user.username === authUser?.name);
  const effectivePermissions = (() => {
    const merged: Record<string, boolean> = {};
    const roleNames = currentUser
      ? (currentUser.roles?.length ? currentUser.roles : currentUser.role.split(',')).map((name) => name.trim()).filter(Boolean)
      : authUser?.name === 'admin'
        ? ['admin']
        : [];

    for (const roleName of roleNames) {
      const role = roleByName.get(roleName);
      if (role?.permissions) Object.assign(merged, role.permissions);
    }
    if (currentUser?.custom_permissions) Object.assign(merged, currentUser.custom_permissions);

    // Labs commonly start with a local mock admin but no persisted users/roles yet.
    if (!Object.keys(merged).length && (!authUser || authUser.name === 'admin')) {
      merged['*'] = true;
    }
    return merged;
  })();

  const canAccess = (permissions?: string[]) =>
    !permissions?.length || !!effectivePermissions['*'] || permissions.some((key) => !!effectivePermissions[key]);

  const visibleSubmenus = (cat: Category) => {
    const submenuPermissions = SUBMENU_PERMISSIONS[cat.key] || {};
    return cat.submenus.filter((submenu) => canAccess(submenuPermissions[submenu]));
  };

  const categoryIsAccessible = (cat: Category) =>
    canAccess(CATEGORY_PERMISSIONS[cat.key]) && visibleSubmenus(cat).length > 0;

  const accessibleCategories = CATEGORIES.filter(categoryIsAccessible);
  const visibleCategories = (normalizedSearch
    ? accessibleCategories.filter((cat) => settingsSearchText({ ...cat, submenus: visibleSubmenus(cat) }).includes(normalizedSearch))
    : accessibleCategories);

  const handleSelect = (key: CategoryKey) => {
    if (!accessibleCategories.some((cat) => cat.key === key)) return;
    setActive(key);
    setSearchParams({ section: key }, { replace: true });
  };

  const activeCategory = CATEGORIES.find((cat) => cat.key === active) ?? CATEGORIES[0];
  const activeSubmenus = visibleSubmenus(activeCategory);
  const dismissSectionIntro = ({ dontShowAgain }: { dontShowAgain: boolean }) => {
    if (dontShowAgain) window.localStorage.setItem(`${SETTINGS_SECTION_INTRO_STORAGE_PREFIX}-${active}`, 'true');
    setShowSectionIntro(false);
  };

  // Sync if URL param changes externally (e.g. back/forward navigation).
  useEffect(() => {
    const s = searchParams.get('section');
    const normalized = normalizeSection(s);
    if (normalized !== active) setActive(normalized);
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!accessibleCategories.some((cat) => cat.key === active) && accessibleCategories.length) {
      handleSelect(accessibleCategories[0].key);
    }
  }, [active, accessibleCategories.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setShowSectionIntro(window.localStorage.getItem(`${SETTINGS_SECTION_INTRO_STORAGE_PREFIX}-${active}`) !== 'true');
  }, [active]);

  return (
    <div className="p-6 space-y-6">
      <PageHeader
        title="System Settings"
        subtitle="The product allows an administrator to configure or modify the network and system wide settings."
      />

      <div className="grid grid-cols-12 gap-6">
        {showSectionIntro && activeCategory && (
          <SettingsSectionIntro category={activeCategory} submenus={activeSubmenus} onDismiss={dismissSectionIntro} />
        )}
        <aside className="col-span-12 md:col-span-4 lg:col-span-3 space-y-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <Input
              type="search"
              value={settingsSearch}
              onChange={(e) => setSettingsSearch(e.target.value)}
              placeholder="Search settings..."
              className="pl-9 pr-9"
              aria-label="Search settings"
            />
            {settingsSearch && (
              <button
                type="button"
                onClick={() => setSettingsSearch('')}
                className="absolute right-2 top-2 inline-flex h-6 w-6 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
                aria-label="Clear settings search"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {visibleCategories.map((cat) => {
            const allowedSubmenus = visibleSubmenus(cat);
            const matchedSubmenus = normalizedSearch
              ? allowedSubmenus.filter((submenu) => submenu.toLowerCase().includes(normalizedSearch))
              : allowedSubmenus.slice(0, 3);

            return (
              <button
                key={cat.key}
                onClick={() => handleSelect(cat.key)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  active === cat.key
                    ? 'border-cisco-blue bg-cisco-blue/5 ring-1 ring-cisco-blue'
                    : 'border-gray-200 bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-cisco-blue text-xs font-bold text-white">
                    {cat.number}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-cisco-blue dark:text-cisco-blue-light">{cat.icon}</span>
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{cat.title}</h3>
                      {cat.status && (
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                          cat.status === 'live'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                            : cat.status === 'partial'
                              ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                              : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                        }`}>
                          {cat.status}
                        </span>
                      )}
                      {allowedSubmenus.length < cat.submenus.length && (
                        <span title="Some submenus are hidden by permissions" className="text-gray-400">
                          <Lock className="h-3.5 w-3.5" />
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-xs leading-snug text-gray-600 dark:text-gray-400 line-clamp-3">
                      {cat.description}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(matchedSubmenus.length ? matchedSubmenus : allowedSubmenus.slice(0, 3)).slice(0, 3).map((submenu) => (
                        <span key={submenu} className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                          {submenu}
                        </span>
                      ))}
                      {!normalizedSearch && allowedSubmenus.length > 3 && (
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-800">
                          +{allowedSubmenus.length - 3}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                </div>
              </button>
            );
          })}

          {visibleCategories.length === 0 && (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white p-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
              No matching settings sections.
            </div>
          )}
        </aside>

        <main className="col-span-12 md:col-span-8 lg:col-span-9">
          <CategoryContent category={active} />
        </main>
      </div>
    </div>
  );
}

export default Settings;
