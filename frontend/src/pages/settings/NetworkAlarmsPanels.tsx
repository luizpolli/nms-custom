/**
 * Network Devices + Alarms/Events + Inventory panels (P1.5 slice 3b).
 *
 * Extracted from Settings.tsx — zero behaviour changes.
 */

import { useEffect, useState } from 'react';
import { Card, CardHeader } from '../../components/ui/Card';
import { Select } from '../../components/ui/Select';
import { Button, Input } from '../../components/ui';
import { api } from '../../lib/api';
import { useSettingsResource, SettingsSaveBar } from './_shared';
import { AlarmRulesPage } from '../alarms/AlarmRulesPage';
import { MIBsPage } from '../mibs/MIBsPage';

// ─── Network Devices ──────────────────────────────────────────────────────────

interface NetworkCliCfg { ssh_timeout_seconds: number; ssh_port: number; cli_retries: number; max_concurrent_ssh_sessions: number; terminal_length: number; }
interface NetworkSnmpCfg { snmp_version: 'v2c' | 'v3'; snmp_community: string; snmp_port: number; snmp_timeout_seconds: number; snmp_retries: number; polling_interval_seconds: number; }
interface NetworkDeviceAdminSettings { cli: NetworkCliCfg; snmp: NetworkSnmpCfg; }

const NETWORK_DEFAULTS: NetworkDeviceAdminSettings = {
  cli: { ssh_timeout_seconds: 30, ssh_port: 22, cli_retries: 2, max_concurrent_ssh_sessions: 10, terminal_length: 0 },
  snmp: { snmp_version: 'v2c', snmp_community: 'public', snmp_port: 161, snmp_timeout_seconds: 5, snmp_retries: 2, polling_interval_seconds: 60 },
};

export function NetworkDevicesPanel() {
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

// ─── Alarms / Events ──────────────────────────────────────────────────────────

interface AlarmSeverityMapping { critical_oid_value: number; major_oid_value: number; minor_oid_value: number; warning_oid_value: number; info_oid_value: number; }
interface AlarmNotificationCfg { email_enabled: boolean; email_recipients: string; syslog_forward_enabled: boolean; syslog_forward_host: string; syslog_forward_port: number; min_severity_to_notify: string; }
interface AlarmSuppressionCfg { suppression_window_minutes: number; flap_detection_enabled: boolean; flap_threshold_count: number; }
interface AlarmsEventsAdminSettings { severity_mapping: AlarmSeverityMapping; notifications: AlarmNotificationCfg; suppression: AlarmSuppressionCfg; }

const ALARMS_DEFAULTS: AlarmsEventsAdminSettings = {
  severity_mapping: { critical_oid_value: 1, major_oid_value: 2, minor_oid_value: 3, warning_oid_value: 4, info_oid_value: 5 },
  notifications: { email_enabled: false, email_recipients: '', syslog_forward_enabled: false, syslog_forward_host: '', syslog_forward_port: 514, min_severity_to_notify: 'major' },
  suppression: { suppression_window_minutes: 5, flap_detection_enabled: true, flap_threshold_count: 3 },
};

export function AlarmsEventsPanel() {
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

// ─── Inventory Settings ───────────────────────────────────────────────────────

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

export function InventorySettingsPanel() {
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
