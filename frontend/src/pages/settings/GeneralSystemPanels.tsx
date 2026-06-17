/**
 * General + System + Mail Notification panels (P1.5 slice 3a).
 *
 * Extracted from Settings.tsx — zero behaviour changes.
 */

import { useEffect, useState } from 'react';
import { FlaskConical } from 'lucide-react';
import { useThemeStore, type Theme } from '../../stores/theme';
import { Card, CardHeader } from '../../components/ui/Card';
import { Select } from '../../components/ui/Select';
import { Button, Input, Badge } from '../../components/ui';
import { api } from '../../lib/api';
import { isDemoEnabled, setDemoMode } from '../../demo/index';
import {
  useSettingsResource,
  SettingsSaveBar,
  SettingsHint,
} from './_shared';

// ─── Demo Mode ────────────────────────────────────────────────────────────────

export function DemoModePanel() {
  const [active, setActive] = useState(isDemoEnabled());

  const toggle = () => {
    setActive(!active);
    setDemoMode(!active);
  };

  return (
    <Card>
      <CardHeader title="Demo Mode" />
      <div className="space-y-4 p-4 text-sm">
        <p className="text-gray-600 dark:text-gray-300">
          Demo Mode injects synthetic data (15 Cisco devices, 25 alarms, 8 services, topology graph,
          credential profiles, and dashboard KPIs) without hitting the real backend. Useful for
          presentations, UAT, and UI development.
        </p>
        <div className="flex items-center gap-4">
          <button
            onClick={toggle}
            role="switch"
            aria-checked={active}
            className={`
              relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center
              rounded-full border-2 border-transparent transition-colors
              focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2
              ${active ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-4 w-4 transform rounded-full
                bg-white shadow transition-transform
                ${active ? 'translate-x-5' : 'translate-x-0.5'}
              `}
            />
          </button>
          <span className="flex items-center gap-1.5 font-medium">
            <FlaskConical className="h-4 w-4 text-amber-600" />
            Demo Mode is <strong>{active ? 'ON' : 'OFF'}</strong>
          </span>
        </div>
        {active && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900 dark:border-amber-600 dark:bg-amber-900/20 dark:text-amber-200">
            Synthetic data is active. Toggling off will reload the page and restore live data.
          </div>
        )}
        <p className="text-xs text-gray-400 dark:text-gray-500">
          Demo state is stored in localStorage and survives page refreshes. It does not affect the
          backend in any way.
        </p>
      </div>
    </Card>
  );
}

// ─── General ─────────────────────────────────────────────────────────────────

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

export function GeneralPanel() {
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

// ─── System ───────────────────────────────────────────────────────────────────

interface SystemMailCfg { smtp_host: string; smtp_port: number; smtp_from: string; smtp_use_tls: boolean; smtp_username: string; }
interface SystemJobsCfg { job_concurrency: number; job_retry_backoff_seconds: number; job_max_retries: number; }
interface SystemRetentionCfg { alarm_retention_days: number; event_retention_days: number; kpi_retention_days: number; telemetry_sample_retention_days: number; }
export interface SystemAdminSettings { mail: SystemMailCfg; jobs: SystemJobsCfg; retention: SystemRetentionCfg; }

export const SYSTEM_DEFAULTS: SystemAdminSettings = {
  mail: { smtp_host: '', smtp_port: 587, smtp_from: '', smtp_use_tls: true, smtp_username: '' },
  jobs: { job_concurrency: 4, job_retry_backoff_seconds: 30, job_max_retries: 3 },
  retention: { alarm_retention_days: 90, event_retention_days: 30, kpi_retention_days: 365, telemetry_sample_retention_days: 7 },
};

export function SystemPanel() {
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

// ─── Mail Notifications ───────────────────────────────────────────────────────

export function MailNotificationPanel() {
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
