import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, ShieldCheck } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select, pushToast } from '../../components/ui';

interface Credential {
  id: string;
  name: string;
}

interface Device {
  id: string;
  name: string;
  ip_address: string;
  device_type: string;
  vendor?: string;
  model?: string;
  os_type?: string;
  status: string;
  location?: string;
  site_id?: string;
  role?: string;
  lifecycle_state?: string;
  platform_family?: string;
  mgmt_vrf?: string;
  snmp_enabled?: boolean;
  ssh_enabled?: boolean;
  tags: string[];
  credential_id?: string | null;
  metadata?: Partial<DeviceFormData>;
}

interface DeviceFormModalProps {
  open: boolean;
  onClose: () => void;
  device?: Device | null;
  initialValues?: Partial<DeviceFormData> | null;
}

type TabKey = 'general' | 'snmp' | 'cli' | 'location';
type SnmpVersion = 'v1' | 'v2c' | 'v3';
type CliProtocol = 'SSH' | 'Telnet';

interface DeviceFormData {
  name: string;
  ip_address: string;
  device_type: string;
  vendor: string;
  model: string;
  os_type: string;
  status: string;
  role: string;
  platform_family: string;
  lifecycle_state: string;
  tags_input: string;
  snmp_enabled: boolean;
  snmp_version: SnmpVersion;
  snmp_read_community: string;
  snmp_write_community: string;
  snmp_port: number;
  snmp_retries: number;
  snmp_timeout: number;
  snmp_v3_username: string;
  snmp_v3_auth_type: string;
  snmp_v3_auth_password: string;
  snmp_v3_privacy_type: string;
  snmp_v3_privacy_password: string;
  ssh_enabled: boolean;
  cli_protocol: CliProtocol;
  cli_port: number;
  cli_username: string;
  cli_password: string;
  cli_enable_password: string;
  cli_timeout: number;
  site_id: string;
  region: string;
  country: string;
  state: string;
  city: string;
  building: string;
  floor: string;
  room: string;
  longitude: string;
  latitude: string;
  mgmt_vrf: string;
  credential_id: string;
}

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'general', label: 'General' },
  { key: 'snmp', label: 'SNMP' },
  { key: 'cli', label: 'CLI / SSH' },
  { key: 'location', label: 'Location' },
];

const EMPTY_FORM: DeviceFormData = {
  name: '',
  ip_address: '',
  device_type: 'router',
  vendor: 'Cisco',
  model: '',
  os_type: '',
  status: 'unknown',
  role: 'other',
  platform_family: '',
  lifecycle_state: 'active',
  tags_input: '',
  snmp_enabled: true,
  snmp_version: 'v2c',
  snmp_read_community: '',
  snmp_write_community: '',
  snmp_port: 161,
  snmp_retries: 2,
  snmp_timeout: 5,
  snmp_v3_username: '',
  snmp_v3_auth_type: 'SHA',
  snmp_v3_auth_password: '',
  snmp_v3_privacy_type: 'AES-128',
  snmp_v3_privacy_password: '',
  ssh_enabled: false,
  cli_protocol: 'SSH',
  cli_port: 22,
  cli_username: '',
  cli_password: '',
  cli_enable_password: '',
  cli_timeout: 30,
  site_id: '',
  region: '',
  country: '',
  state: '',
  city: '',
  building: '',
  floor: '',
  room: '',
  longitude: '',
  latitude: '',
  mgmt_vrf: '',
  credential_id: '',
};

const deviceTypeOptions = ['router', 'switch', 'firewall', 'access-point', 'server', 'other'].map((value) => ({ value, label: value }));
const vendorOptions = ['Cisco', 'Juniper', 'Huawei', 'Nokia', 'Arista', 'Other'].map((value) => ({ value, label: value }));
const statusOptions = ['reachable', 'unreachable', 'unknown'].map((value) => ({ value, label: value }));
const roleOptions = ['core', 'distribution', 'access', 'edge', 'border', 'other'].map((value) => ({ value, label: value }));
const lifecycleOptions = ['active', 'maintenance', 'decommissioned'].map((value) => ({ value, label: value }));

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="grid grid-cols-12 items-center gap-3">
      <span className="col-span-4 text-right text-sm font-medium text-gray-700 dark:text-gray-300">
        {required && <span className="mr-0.5 text-red-500">*</span>}
        {label}
      </span>
      <span className="col-span-8">{children}</span>
    </label>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={clsx(
        'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-cisco-blue focus:ring-offset-2',
        checked ? 'bg-cisco-blue' : 'bg-gray-300 dark:bg-gray-600',
      )}
    >
      <span
        className={clsx(
          'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0',
        )}
      />
    </button>
  );
}

const toSnmpAuth = (value: string) => (value === 'MD5' ? 'HMAC-MD5' : value === 'SHA-256' ? 'SHA-256' : 'HMAC-SHA');
const toSnmpPrivacy = (value: string) => (value === 'DES' ? 'CBC-DES' : value === 'AES-256' ? 'CFB-AES-256' : 'CFB-AES-128');

export function DeviceFormModal({ open, onClose, device, initialValues }: DeviceFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DeviceFormData>(EMPTY_FORM);
  const [tab, setTab] = useState<TabKey>('general');

  const { data: credentials = [] } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    if (device) {
      const meta = device.metadata ?? {};
      setForm({
        ...EMPTY_FORM,
        ...meta,
        name: device.name,
        ip_address: device.ip_address,
        device_type: device.device_type,
        vendor: device.vendor ?? '',
        model: device.model ?? '',
        os_type: device.os_type ?? '',
        status: device.status ?? 'unknown',
        role: device.role ?? 'other',
        platform_family: device.platform_family ?? '',
        lifecycle_state: device.lifecycle_state ?? 'active',
        tags_input: (device.tags ?? []).join(', '),
        snmp_enabled: device.snmp_enabled ?? true,
        ssh_enabled: device.ssh_enabled ?? false,
        site_id: device.site_id ?? device.location ?? '',
        mgmt_vrf: device.mgmt_vrf ?? '',
        credential_id: device.credential_id ?? '',
      } as DeviceFormData);
    } else {
      setForm({ ...EMPTY_FORM, ...initialValues } as DeviceFormData);
    }
    setTab('general');
  }, [device, initialValues, open]);

  const set = <K extends keyof DeviceFormData>(key: K, value: DeviceFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const tags = useMemo(
    () => form.tags_input.split(',').map((tag) => tag.trim()).filter(Boolean),
    [form.tags_input],
  );

  const createCredentialFromForm = async (data: DeviceFormData) => {
    if (data.credential_id) return data.credential_id;

    const hasSnmpCredential =
      data.snmp_enabled &&
      (data.snmp_version === 'v3' ? !!data.snmp_v3_username : !!data.snmp_read_community);
    const hasCliCredential = data.ssh_enabled && !!data.cli_password;

    if (!hasSnmpCredential && !hasCliCredential) return null;

    const useCli = hasCliCredential && !hasSnmpCredential;
    const secret = useCli
      ? data.cli_password
      : data.snmp_version === 'v3'
        ? data.snmp_v3_auth_password || data.snmp_v3_privacy_password || data.snmp_v3_username
        : data.snmp_read_community;

    const credPayload: Record<string, unknown> = {
      name: `${data.name || data.ip_address}-cred`,
      hostname: data.ip_address,
      username: useCli ? (data.cli_username || 'admin') : (data.snmp_version === 'v3' ? (data.snmp_v3_username || 'snmpuser') : 'community'),
      secret: secret || 'changeme',
      protocol: useCli ? data.cli_protocol.toLowerCase() : 'snmp',
      snmp_version: data.snmp_version,
      port: useCli ? data.cli_port : data.snmp_port,
    };
    if (data.snmp_version === 'v3' && data.snmp_v3_privacy_password) {
      credPayload.enc_secret = data.snmp_v3_privacy_password;
    }
    const response = await api.post('/credentials', credPayload);
    queryClient.invalidateQueries({ queryKey: ['credentials'] });
    return response.data.id as string;
  };

  const mutation = useMutation({
    mutationFn: async (data: DeviceFormData) => {
      const credentialId = await createCredentialFromForm(data);
      const payload: Record<string, unknown> = {
        name: data.name,
        ip_address: data.ip_address,
        device_type: data.device_type,
        vendor: data.vendor || undefined,
        model: data.model || undefined,
        os_type: data.os_type || undefined,
        status: data.status,
        role: data.role || undefined,
        platform_family: data.platform_family || undefined,
        lifecycle_state: data.lifecycle_state,
        location: data.site_id || undefined,
        site_id: data.site_id || undefined,
        mgmt_vrf: data.mgmt_vrf || undefined,
        snmp_enabled: data.snmp_enabled,
        ssh_enabled: data.ssh_enabled,
        tags,
      };
      if (credentialId) payload.credential_id = credentialId;
      return device ? api.patch(`/devices/${device.id}`, payload) : api.post('/devices', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      pushToast(device ? 'Device updated successfully' : 'Device created successfully', 'success');
      onClose();
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () =>
      api
        .post('/devices/verify-credentials', {
          ip_address: form.ip_address,
          identification: 'ip',
          snmp: {
            version: form.snmp_version,
            read_community: form.snmp_read_community,
            v3_username: form.snmp_v3_username,
            v3_auth_type: toSnmpAuth(form.snmp_v3_auth_type),
            v3_auth_password: form.snmp_v3_auth_password,
            v3_priv_type: toSnmpPrivacy(form.snmp_v3_privacy_type),
            v3_priv_password: form.snmp_v3_privacy_password,
            port: form.snmp_port,
            timeout: form.snmp_timeout,
            retries: form.snmp_retries,
          },
          telnet_ssh: {
            protocol: form.cli_protocol.toLowerCase(),
            cli_port: form.cli_port,
            timeout: form.cli_timeout,
            username: form.cli_username,
            password: form.cli_password,
            enable_password: form.cli_enable_password,
          },
        })
        .then((r) => r.data as { ok: boolean; sys_descr?: string; error?: string }),
    onSuccess: (data) => {
      if (data.ok) {
        pushToast(data.sys_descr ? `Credentials verified: ${data.sys_descr}` : 'Credentials verified', 'success');
      } else {
        pushToast(`Credential verification failed: ${data.error ?? 'unknown error'}`, 'error');
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title={device ? 'Edit Device' : 'Add Device'} size="3xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-3 dark:border-gray-700">
          {TABS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={clsx(
                'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                tab === item.key
                  ? 'bg-cisco-blue text-white'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
              )}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="max-h-[60vh] overflow-y-auto pr-1">
          {tab === 'general' && (
            <section className="grid grid-cols-2 gap-x-6 gap-y-3">
              <Field label="Device Name" required><Input value={form.name} onChange={(e) => set('name', e.target.value)} required /></Field>
              <Field label="IP Address" required><Input value={form.ip_address} onChange={(e) => set('ip_address', e.target.value)} required /></Field>
              <Field label="Device Type"><Select value={form.device_type} onChange={(e) => set('device_type', e.target.value)} options={deviceTypeOptions} /></Field>
              <Field label="Vendor"><Select value={form.vendor} onChange={(e) => set('vendor', e.target.value)} options={vendorOptions} /></Field>
              <Field label="Model"><Input value={form.model} onChange={(e) => set('model', e.target.value)} /></Field>

              <Field label="Status"><Select value={form.status} onChange={(e) => set('status', e.target.value)} options={statusOptions} /></Field>
              <Field label="Role"><Select value={form.role} onChange={(e) => set('role', e.target.value)} options={roleOptions} /></Field>
              <Field label="Platform Family"><Input value={form.platform_family} onChange={(e) => set('platform_family', e.target.value)} /></Field>
              <Field label="Lifecycle State"><Select value={form.lifecycle_state} onChange={(e) => set('lifecycle_state', e.target.value)} options={lifecycleOptions} /></Field>
              <div className="col-span-2">
                <Field label="Tags"><Input value={form.tags_input} onChange={(e) => set('tags_input', e.target.value)} placeholder="core, cdmx, production" /></Field>
              </div>
              <div className="col-span-2 mt-2 border-t border-gray-200 pt-3 dark:border-gray-700">
                <Field label="Credential Profile">
                  <Select
                    value={form.credential_id}
                    onChange={(e) => set('credential_id', e.target.value)}
                    options={[{ value: '', label: '— Create from SNMP/CLI tabs —' }, ...credentials.map((c) => ({ value: c.id, label: c.name }))]}
                  />
                </Field>
                {form.credential_id && (
                  <p className="mt-1 ml-[33.33%] text-xs text-green-600 dark:text-green-400">
                    ✓ Using existing credential profile. SNMP/CLI tabs are optional.
                  </p>
                )}
                {!form.credential_id && (
                  <p className="mt-1 ml-[33.33%] text-xs text-gray-500 dark:text-gray-400">
                    No profile selected — fill SNMP or CLI tab to create one on save.
                  </p>
                )}
              </div>
              {form.ip_address && (
                <div className="col-span-2 flex justify-end">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => verifyMutation.mutate()}
                    disabled={verifyMutation.isPending}
                    leftIcon={verifyMutation.isSuccess ? <CheckCircle className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
                  >
                    {verifyMutation.isPending ? 'Verifying...' : 'Verify Credentials'}
                  </Button>
                </div>
              )}
            </section>
          )}

          {tab === 'snmp' && (
            <section className="grid grid-cols-2 gap-x-6 gap-y-3">
              {form.credential_id && (
                <div className="col-span-2 mb-2 rounded-md border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
                  A credential profile is selected. These fields will only be used if you clear the profile in General.
                </div>
              )}
              <Field label="SNMP Enabled"><Toggle checked={form.snmp_enabled} onChange={(value) => set('snmp_enabled', value)} /></Field>
              <Field label="SNMP Version"><Select value={form.snmp_version} onChange={(e) => set('snmp_version', e.target.value as SnmpVersion)} options={[{ value: 'v1', label: 'v1' }, { value: 'v2c', label: 'v2c' }, { value: 'v3', label: 'v3' }]} /></Field>
              <Field label="Read Community"><Input type="password" value={form.snmp_read_community} onChange={(e) => set('snmp_read_community', e.target.value)} disabled={!form.snmp_enabled} /></Field>
              <Field label="Write Community"><Input type="password" value={form.snmp_write_community} onChange={(e) => set('snmp_write_community', e.target.value)} disabled={!form.snmp_enabled} /></Field>
              <Field label="SNMP Port"><Input type="number" value={form.snmp_port} onChange={(e) => set('snmp_port', Number(e.target.value))} disabled={!form.snmp_enabled} /></Field>
              <Field label="SNMP Retries"><Input type="number" value={form.snmp_retries} onChange={(e) => set('snmp_retries', Number(e.target.value))} disabled={!form.snmp_enabled} /></Field>
              <Field label="SNMP Timeout"><Input type="number" value={form.snmp_timeout} onChange={(e) => set('snmp_timeout', Number(e.target.value))} disabled={!form.snmp_enabled} /></Field>
              {form.snmp_version === 'v3' && (
                <>
                  <Field label="Username"><Input value={form.snmp_v3_username} onChange={(e) => set('snmp_v3_username', e.target.value)} disabled={!form.snmp_enabled} /></Field>
                  <Field label="Auth Type"><Select value={form.snmp_v3_auth_type} onChange={(e) => set('snmp_v3_auth_type', e.target.value)} disabled={!form.snmp_enabled} options={[{ value: 'MD5', label: 'MD5' }, { value: 'SHA', label: 'SHA' }, { value: 'SHA-256', label: 'SHA-256' }]} /></Field>
                  <Field label="Auth Password"><Input type="password" value={form.snmp_v3_auth_password} onChange={(e) => set('snmp_v3_auth_password', e.target.value)} disabled={!form.snmp_enabled} /></Field>
                  <Field label="Privacy Type"><Select value={form.snmp_v3_privacy_type} onChange={(e) => set('snmp_v3_privacy_type', e.target.value)} disabled={!form.snmp_enabled} options={[{ value: 'DES', label: 'DES' }, { value: 'AES-128', label: 'AES-128' }, { value: 'AES-256', label: 'AES-256' }]} /></Field>
                  <Field label="Privacy Password"><Input type="password" value={form.snmp_v3_privacy_password} onChange={(e) => set('snmp_v3_privacy_password', e.target.value)} disabled={!form.snmp_enabled} /></Field>
                </>
              )}
            </section>
          )}

          {tab === 'cli' && (
            <section className="grid grid-cols-2 gap-x-6 gap-y-3">
              {form.credential_id && (
                <div className="col-span-2 mb-2 rounded-md border border-blue-200 bg-blue-50 px-4 py-2 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300">
                  A credential profile is selected. These fields will only be used if you clear the profile in General.
                </div>
              )}
              <Field label="SSH Enabled"><Toggle checked={form.ssh_enabled} onChange={(value) => set('ssh_enabled', value)} /></Field>
              <Field label="Protocol"><Select value={form.cli_protocol} onChange={(e) => set('cli_protocol', e.target.value as CliProtocol)} options={[{ value: 'SSH', label: 'SSH' }, { value: 'Telnet', label: 'Telnet' }]} disabled={!form.ssh_enabled} /></Field>
              <Field label="CLI Port"><Input type="number" value={form.cli_port} onChange={(e) => set('cli_port', Number(e.target.value))} disabled={!form.ssh_enabled} /></Field>
              <Field label="CLI Username"><Input value={form.cli_username} onChange={(e) => set('cli_username', e.target.value)} disabled={!form.ssh_enabled} /></Field>
              <Field label="CLI Password"><Input type="password" value={form.cli_password} onChange={(e) => set('cli_password', e.target.value)} disabled={!form.ssh_enabled} /></Field>
              <Field label="Enable Password"><Input type="password" value={form.cli_enable_password} onChange={(e) => set('cli_enable_password', e.target.value)} disabled={!form.ssh_enabled} /></Field>
              <Field label="CLI Timeout"><Input type="number" value={form.cli_timeout} onChange={(e) => set('cli_timeout', Number(e.target.value))} disabled={!form.ssh_enabled} /></Field>
            </section>
          )}

          {tab === 'location' && (
            <section className="grid grid-cols-2 gap-x-6 gap-y-3">
              <Field label="Site / Location Group"><Input value={form.site_id} onChange={(e) => set('site_id', e.target.value)} /></Field>
              <Field label="Region"><Input value={form.region} onChange={(e) => set('region', e.target.value)} /></Field>
              <Field label="Country"><Input value={form.country} onChange={(e) => set('country', e.target.value)} /></Field>
              <Field label="State"><Input value={form.state} onChange={(e) => set('state', e.target.value)} /></Field>
              <Field label="City"><Input value={form.city} onChange={(e) => set('city', e.target.value)} /></Field>
              <Field label="Building"><Input value={form.building} onChange={(e) => set('building', e.target.value)} /></Field>
              <Field label="Floor"><Input value={form.floor} onChange={(e) => set('floor', e.target.value)} /></Field>
              <Field label="Room"><Input value={form.room} onChange={(e) => set('room', e.target.value)} /></Field>
              <Field label="Longitude"><Input value={form.longitude} onChange={(e) => set('longitude', e.target.value)} /></Field>
              <Field label="Latitude"><Input value={form.latitude} onChange={(e) => set('latitude', e.target.value)} /></Field>
              <Field label="Management VRF"><Input value={form.mgmt_vrf} onChange={(e) => set('mgmt_vrf', e.target.value)} /></Field>
            </section>
          )}


        </div>

        <div className="flex justify-end gap-2 border-t border-gray-200 pt-4 dark:border-gray-700">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving...' : device ? 'Save' : 'Add'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
