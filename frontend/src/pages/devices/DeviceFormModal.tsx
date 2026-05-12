import { useState, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check } from 'lucide-react';
import { clsx } from 'clsx';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select } from '../../components/ui';

interface Credential {
  id: string;
  name: string;
}

interface SnmpParams {
  version: 'v1' | 'v2c' | 'v3';
  retries: number;
  timeout: number;
  port: number;
  read_community: string;
  confirm_read_community: string;
  write_community: string;
  confirm_write_community: string;
  v3_username: string;
  v3_mode: 'AuthPriv' | 'AuthNoPriv' | 'NoAuthNoPriv';
  v3_auth_type: 'none' | 'HMAC-MD5' | 'HMAC-SHA';
  v3_auth_password: string;
  v3_priv_type: 'CBC-DES' | 'CFB-AES-128' | 'CFB-AES-196' | 'CFB-AES-256';
  v3_priv_password: string;
}

interface TelnetSshParams {
  protocol: 'telnet' | 'ssh2' | 'netconf-ssh2';
  cli_port: number;
  timeout: number;
  username: string;
  password: string;
  confirm_password: string;
  enable_password: string;
  confirm_enable_password: string;
}

interface HttpParams {
  protocol: 'http' | 'https';
  tcp_port: number;
  username: string;
  password: string;
  confirm_password: string;
  monitor_username: string;
  monitor_password: string;
  confirm_monitor_password: string;
}

interface Tl1Params {
  protocol: 'telnet' | 'ssh';
  single_session: 'enabled' | 'disabled';
  primary_proxy_ip: string;
  secondary_proxy_ip: string;
  username: string;
  password: string;
  confirm_password: string;
}

interface CivicLocation {
  region: string;
  country: string;
  state: string;
  city: string;
  county: string;
  street: string;
  building: string;
  floor: string;
  room: string;
  longitude: string;
  latitude: string;
}

interface UserDefinedField {
  key: string;
  value: string;
}

interface DeviceFormData {
  // General
  identification: 'ip' | 'dns';
  ip_address: string;
  dns_name: string;
  device_role: string;
  group: string;
  new_group: string;
  credential_id: string;
  // Legacy fields (still on backend Device model)
  name: string;
  device_type: string;
  vendor: string;
  model: string;
  os_type: string;
  location: string;
  tags: string[];
  // Extended (stored in metadata blob)
  snmp: SnmpParams;
  telnet_ssh: TelnetSshParams;
  http: HttpParams;
  tl1: Tl1Params;
  civic_location: CivicLocation;
  user_defined_fields: UserDefinedField[];
}

interface Device {
  id: string;
  name: string;
  ip_address: string;
  device_type: string;
  vendor: string;
  model: string;
  os_type: string;
  location: string;
  tags: string[];
  credential_id: string;
  status: string;
  metadata?: Partial<DeviceFormData>;
}

interface DeviceFormModalProps {
  open: boolean;
  onClose: () => void;
  device?: Device | null;
  initialValues?: Partial<DeviceFormData> | null;
}

type TabKey = 'general' | 'snmp' | 'telnet_ssh' | 'http' | 'tl1' | 'civic' | 'udf';

interface TabDef {
  key: TabKey;
  label: string;
  required?: boolean;
  hint?: string;
}

const TABS: TabDef[] = [
  { key: 'general', label: 'General', required: true },
  { key: 'snmp', label: 'SNMP', required: true, hint: 'Optional if TL1/Netconf is configured' },
  { key: 'telnet_ssh', label: 'Telnet/SSH' },
  { key: 'http', label: 'HTTP/HTTPS' },
  { key: 'tl1', label: 'TL1' },
  { key: 'civic', label: 'Civic Location' },
  { key: 'udf', label: 'User Defined Fields' },
];

const DEVICE_ROLE_OPTIONS = [
  { value: '', label: '--Select--' },
  { value: 'access_router', label: 'Access Router' },
  { value: 'aggregation_router', label: 'Aggregation Router' },
  { value: 'branch_switch', label: 'Branch Switch' },
  { value: 'border_router', label: 'Border Router' },
  { value: 'core_switch', label: 'Core Switch' },
  { value: 'campus_switch', label: 'Campus Switch' },
  { value: 'distribution_switch', label: 'Distribution Switch' },
  { value: 'dmvpn_spoke_router', label: 'DMVPN Spoke Router' },
  { value: 'data_center_switch', label: 'Data Center Switch' },
  { value: 'hub_router', label: 'Hub Router' },
  { value: 'master_controller', label: 'Master Controller' },
  { value: 'unknown', label: 'Unknown' },
];

const NEW_GROUP_SENTINEL = '__new__';

const REGION_OPTIONS = [
  { value: '', label: '--Select--' },
  { value: 'NA', label: 'North America' },
  { value: 'LATAM', label: 'Latin America' },
  { value: 'EMEA', label: 'EMEA' },
  { value: 'APAC', label: 'APAC' },
];

const EMPTY_FORM: DeviceFormData = {
  identification: 'ip',
  ip_address: '',
  dns_name: '',
  device_role: '',
  group: '',
  new_group: '',
  credential_id: '',
  name: '',
  device_type: 'router',
  vendor: '',
  model: '',
  os_type: 'ios-xr',
  location: '',
  tags: [],
  snmp: {
    version: 'v2c',
    retries: 2,
    timeout: 10,
    port: 161,
    read_community: '',
    confirm_read_community: '',
    write_community: '',
    confirm_write_community: '',
    v3_username: '',
    v3_mode: 'AuthPriv',
    v3_auth_type: 'HMAC-SHA',
    v3_auth_password: '',
    v3_priv_type: 'CFB-AES-128',
    v3_priv_password: '',
  },
  telnet_ssh: {
    protocol: 'telnet',
    cli_port: 23,
    timeout: 60,
    username: '',
    password: '',
    confirm_password: '',
    enable_password: '',
    confirm_enable_password: '',
  },
  http: {
    protocol: 'http',
    tcp_port: 80,
    username: '',
    password: '',
    confirm_password: '',
    monitor_username: '',
    monitor_password: '',
    confirm_monitor_password: '',
  },
  tl1: {
    protocol: 'telnet',
    single_session: 'disabled',
    primary_proxy_ip: '',
    secondary_proxy_ip: '',
    username: '',
    password: '',
    confirm_password: '',
  },
  civic_location: {
    region: '',
    country: '',
    state: '',
    city: '',
    county: '',
    street: '',
    building: '',
    floor: '',
    room: '',
    longitude: '',
    latitude: '',
  },
  user_defined_fields: [],
};

function FieldRow({ label, required, children, hint }: { label: string; required?: boolean; children: React.ReactNode; hint?: string }) {
  return (
    <div className="grid grid-cols-12 items-center gap-3 py-1.5">
      <label className="col-span-4 text-right text-sm font-medium text-gray-700 dark:text-gray-300">
        {required && <span className="text-red-500 mr-0.5">*</span>}
        {label}
      </label>
      <div className="col-span-8">
        {children}
        {hint && <p className="text-xs text-gray-500 mt-1">{hint}</p>}
      </div>
    </div>
  );
}

export function DeviceFormModal({ open, onClose, device, initialValues }: DeviceFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DeviceFormData>(EMPTY_FORM);
  const [tab, setTab] = useState<TabKey>('general');
  const [completed, setCompleted] = useState<Set<TabKey>>(new Set());

  const { data: credentials = [] } = useQuery<Credential[]>({
    queryKey: ['credentials'],
    queryFn: () => api.get('/credentials').then((r) => r.data),
    enabled: open,
  });

  const { data: existingDevices = [] } = useQuery<{ tags?: string[] }[]>({
    queryKey: ['devices', 'for-groups'],
    queryFn: () => api.get('/devices', { params: { limit: 1000 } }).then((r) => r.data),
    enabled: open,
  });

  const existingGroups = Array.from(
    new Set(
      existingDevices
        .flatMap((d) => d.tags ?? [])
        .filter((t) => typeof t === 'string' && t.startsWith('group:'))
        .map((t) => t.slice('group:'.length)),
    ),
  ).sort();

  const groupOptions = [
    { value: '', label: '--Select--' },
    ...existingGroups.map((g) => ({ value: g, label: g })),
    { value: NEW_GROUP_SENTINEL, label: '+ Create new group...' },
  ];

  useEffect(() => {
    if (!open) return;
    if (device) {
      setForm({
        ...EMPTY_FORM,
        ...device.metadata,
        identification: 'ip',
        ip_address: device.ip_address,
        name: device.name,
        device_type: device.device_type,
        vendor: device.vendor,
        model: device.model,
        os_type: device.os_type,
        location: device.location,
        tags: device.tags ?? [],
        credential_id: device.credential_id ?? '',
      } as DeviceFormData);
    } else {
      setForm({ ...EMPTY_FORM, ...initialValues } as DeviceFormData);
    }
    setTab('general');
    setCompleted(new Set());
  }, [device, initialValues, open]);

  const set = <K extends keyof DeviceFormData>(key: K, value: DeviceFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const setNested = <S extends 'snmp' | 'telnet_ssh' | 'http' | 'tl1' | 'civic_location'>(
    section: S,
    key: keyof DeviceFormData[S],
    value: unknown,
  ) => {
    setForm((prev) => ({ ...prev, [section]: { ...prev[section], [key]: value } as DeviceFormData[S] }));
  };

  const markComplete = (key: TabKey) => setCompleted((s) => new Set(s).add(key));

  const mutation = useMutation({
    mutationFn: (data: DeviceFormData) => {
      const resolvedGroup =
        data.group === NEW_GROUP_SENTINEL
          ? data.new_group.trim()
          : data.group;
      const baseTags = (data.tags ?? []).filter((t) => !t.startsWith('group:'));
      const tags = resolvedGroup ? [...baseTags, `group:${resolvedGroup}`] : baseTags;
      const payload = {
        name: data.name || data.ip_address,
        ip_address: data.identification === 'ip' ? data.ip_address : data.dns_name,
        device_type: data.device_type,
        vendor: data.vendor,
        model: data.model,
        os_type: data.os_type,
        location: data.location,
        tags,
        credential_id: data.credential_id || null,
        metadata: {
          identification: data.identification,
          dns_name: data.dns_name,
          device_role: data.device_role,
          group: resolvedGroup,
          snmp: data.snmp,
          telnet_ssh: data.telnet_ssh,
          http: data.http,
          tl1: data.tl1,
          civic_location: data.civic_location,
          user_defined_fields: data.user_defined_fields,
        },
      };
      return device ? api.patch(`/devices/${device.id}`, payload) : api.post('/devices', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      onClose();
    },
    onError: (err) => {
      console.error('Save device failed', err);
      alert('Failed to save device');
    },
  });

  const verifyMutation = useMutation({
    mutationFn: () =>
      api
        .post('/devices/verify-credentials', {
          ip_address: form.ip_address,
          dns_name: form.dns_name,
          identification: form.identification,
          snmp: {
            version: form.snmp.version,
            read_community: form.snmp.read_community,
            v3_username: form.snmp.v3_username,
            v3_auth_type: form.snmp.v3_auth_type,
            v3_auth_password: form.snmp.v3_auth_password,
            v3_priv_type: form.snmp.v3_priv_type,
            v3_priv_password: form.snmp.v3_priv_password,
            port: form.snmp.port,
            timeout: form.snmp.timeout,
            retries: form.snmp.retries,
          },
          telnet_ssh: form.telnet_ssh,
          http: form.http,
        })
        .then((r) => r.data as { ok: boolean; sys_descr?: string; error?: string }),
    onSuccess: (data) => {
      if (data.ok) {
        alert(`Credentials verified.\n${data.sys_descr ? `sysDescr: ${data.sys_descr}` : ''}`);
      } else {
        alert(`Credential verification failed: ${data.error ?? 'unknown error'}`);
      }
    },
    onError: (err: Error) => {
      console.error('Verify failed', err);
      alert('Credential verification failed');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    markComplete(tab);
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title="Add Device" size="2xl">
      <form onSubmit={handleSubmit} className="flex gap-6">
        {/* Tab rail */}
        <div className="w-44 shrink-0">
          <div className="space-y-2">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => { markComplete(tab); setTab(t.key); }}
                className={clsx(
                  'w-full rounded-md border px-3 py-2 text-left text-sm transition-colors',
                  tab === t.key
                    ? 'border-cisco-blue bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100 ring-1 ring-cisco-blue'
                    : 'border-gray-200 bg-gray-50 text-gray-700 hover:bg-white dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300',
                )}
              >
                <div className="flex items-center justify-between">
                  <span>
                    {t.required && <span className="text-red-500 mr-1">*</span>}
                    {t.label}
                  </span>
                  {completed.has(t.key) && tab !== t.key && <Check className="h-4 w-4 text-green-500" />}
                </div>
                {t.hint && <p className="mt-1 text-[11px] leading-tight text-gray-500">({t.hint})</p>}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div className="flex-1 min-w-0 rounded-md border border-gray-200 dark:border-gray-700 p-5">
          {tab === 'general' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">
                <span className="text-red-500 mr-1">*</span>General Parameters
              </h3>
              <div className="grid grid-cols-12 items-center gap-3 py-1.5">
                <label className="col-span-4 text-right text-sm font-medium text-gray-700 dark:text-gray-300">
                  <input
                    type="radio"
                    name="ident"
                    checked={form.identification === 'ip'}
                    onChange={() => set('identification', 'ip')}
                    className="mr-2"
                  />
                  IP Address
                </label>
                <div className="col-span-8">
                  <Input
                    value={form.ip_address}
                    onChange={(e) => set('ip_address', e.target.value)}
                    disabled={form.identification !== 'ip'}
                    required={form.identification === 'ip'}
                  />
                </div>
              </div>
              <div className="grid grid-cols-12 items-center gap-3 py-1.5">
                <label className="col-span-4 text-right text-sm font-medium text-gray-700 dark:text-gray-300">
                  <input
                    type="radio"
                    name="ident"
                    checked={form.identification === 'dns'}
                    onChange={() => set('identification', 'dns')}
                    className="mr-2"
                  />
                  DNS Name
                </label>
                <div className="col-span-8">
                  <Input
                    value={form.dns_name}
                    onChange={(e) => set('dns_name', e.target.value)}
                    disabled={form.identification !== 'dns'}
                  />
                </div>
              </div>
              <FieldRow label="Device Role">
                <Select value={form.device_role} onChange={(e) => set('device_role', e.target.value)} options={DEVICE_ROLE_OPTIONS} />
              </FieldRow>
              <FieldRow
                label="Add to Group"
                hint="Pick an existing group, create a new one, or leave blank to auto-categorize by SNMP-detected device type."
              >
                <Select
                  value={form.group}
                  onChange={(e) => set('group', e.target.value)}
                  options={groupOptions}
                />
              </FieldRow>
              {form.group === NEW_GROUP_SENTINEL && (
                <FieldRow label="New Group Name" required>
                  <Input
                    value={form.new_group}
                    onChange={(e) => set('new_group', e.target.value)}
                    placeholder="e.g. site-cdmx, ring-norte"
                    required
                  />
                </FieldRow>
              )}
              <FieldRow label="Credential Profile">
                <Select
                  value={form.credential_id}
                  onChange={(e) => set('credential_id', e.target.value)}
                  options={[{ value: '', label: '--Select--' }, ...credentials.map((c) => ({ value: c.id, label: c.name }))]}
                />
              </FieldRow>
            </section>
          )}

          {tab === 'snmp' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">
                <span className="text-red-500 mr-1">*</span>SNMP Parameters
              </h3>
              <FieldRow label="Version">
                <Select
                  value={form.snmp.version}
                  onChange={(e) => setNested('snmp', 'version', e.target.value as SnmpParams['version'])}
                  options={[{ value: 'v1', label: 'v1' }, { value: 'v2c', label: 'v2c' }, { value: 'v3', label: 'v3' }]}
                />
              </FieldRow>
              <FieldRow label="SNMP Retries" required>
                <Input type="number" value={form.snmp.retries} onChange={(e) => setNested('snmp', 'retries', Number(e.target.value))} />
              </FieldRow>
              <FieldRow label="SNMP Timeout" required>
                <Input type="number" value={form.snmp.timeout} onChange={(e) => setNested('snmp', 'timeout', Number(e.target.value))} />
              </FieldRow>
              <FieldRow label="SNMP Port" required>
                <Input type="number" value={form.snmp.port} onChange={(e) => setNested('snmp', 'port', Number(e.target.value))} />
              </FieldRow>
              {form.snmp.version !== 'v3' ? (
                <>
                  <FieldRow label="Read Community" required>
                    <Input type="password" value={form.snmp.read_community} onChange={(e) => setNested('snmp', 'read_community', e.target.value)} />
                  </FieldRow>
                  <FieldRow label="Confirm Read Community" required>
                    <Input type="password" value={form.snmp.confirm_read_community} onChange={(e) => setNested('snmp', 'confirm_read_community', e.target.value)} />
                  </FieldRow>
                  <FieldRow label="Write Community">
                    <Input type="password" value={form.snmp.write_community} onChange={(e) => setNested('snmp', 'write_community', e.target.value)} />
                  </FieldRow>
                  <FieldRow label="Confirm Write Community">
                    <Input type="password" value={form.snmp.confirm_write_community} onChange={(e) => setNested('snmp', 'confirm_write_community', e.target.value)} />
                  </FieldRow>
                </>
              ) : (
                <>
                  <FieldRow label="Username" required>
                    <Input value={form.snmp.v3_username} onChange={(e) => setNested('snmp', 'v3_username', e.target.value)} />
                  </FieldRow>
                  <FieldRow label="Mode" required>
                    <Select
                      value={form.snmp.v3_mode}
                      onChange={(e) => setNested('snmp', 'v3_mode', e.target.value as SnmpParams['v3_mode'])}
                      options={[{ value: 'AuthPriv', label: 'AuthPriv' }, { value: 'AuthNoPriv', label: 'AuthNoPriv' }, { value: 'NoAuthNoPriv', label: 'NoAuthNoPriv' }]}
                    />
                  </FieldRow>
                  <FieldRow label="Auth. Type">
                    <Select
                      value={form.snmp.v3_auth_type}
                      onChange={(e) => setNested('snmp', 'v3_auth_type', e.target.value as SnmpParams['v3_auth_type'])}
                      disabled={form.snmp.v3_mode === 'NoAuthNoPriv'}
                      options={[{ value: 'none', label: 'none' }, { value: 'HMAC-MD5', label: 'HMAC-MD5' }, { value: 'HMAC-SHA', label: 'HMAC-SHA' }]}
                    />
                  </FieldRow>
                  <FieldRow label="Auth. Password">
                    <Input type="password" value={form.snmp.v3_auth_password} onChange={(e) => setNested('snmp', 'v3_auth_password', e.target.value)} disabled={form.snmp.v3_mode === 'NoAuthNoPriv' || form.snmp.v3_auth_type === 'none'} />
                  </FieldRow>
                  <FieldRow label="Priv. Type">
                    <Select
                      value={form.snmp.v3_priv_type}
                      onChange={(e) => setNested('snmp', 'v3_priv_type', e.target.value as SnmpParams['v3_priv_type'])}
                      disabled={form.snmp.v3_mode !== 'AuthPriv'}
                      options={[{ value: 'CBC-DES', label: 'CBC-DES' }, { value: 'CFB-AES-128', label: 'CFB-AES-128' }, { value: 'CFB-AES-196', label: 'CFB-AES-196' }, { value: 'CFB-AES-256', label: 'CFB-AES-256' }]}
                    />
                  </FieldRow>
                  <FieldRow label="Priv. Password">
                    <Input type="password" value={form.snmp.v3_priv_password} onChange={(e) => setNested('snmp', 'v3_priv_password', e.target.value)} disabled={form.snmp.v3_mode !== 'AuthPriv'} />
                  </FieldRow>
                </>
              )}
            </section>
          )}

          {tab === 'telnet_ssh' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">Telnet/SSH Parameters</h3>
              <FieldRow label="Protocol">
                <Select
                  value={form.telnet_ssh.protocol}
                  onChange={(e) => setNested('telnet_ssh', 'protocol', e.target.value as TelnetSshParams['protocol'])}
                  options={[
                    { value: 'telnet', label: 'Telnet' },
                    { value: 'ssh2', label: 'SSH2' },
                    { value: 'netconf-ssh2', label: 'Netconf Over SSH2' },
                  ]}
                />
              </FieldRow>
              <FieldRow label="CLI Port" required>
                <Input type="number" value={form.telnet_ssh.cli_port} onChange={(e) => setNested('telnet_ssh', 'cli_port', Number(e.target.value))} />
              </FieldRow>
              <FieldRow label="Timeout (Secs)" required>
                <Input type="number" value={form.telnet_ssh.timeout} onChange={(e) => setNested('telnet_ssh', 'timeout', Number(e.target.value))} />
              </FieldRow>
              <FieldRow label="Username">
                <Input value={form.telnet_ssh.username} onChange={(e) => setNested('telnet_ssh', 'username', e.target.value)} />
              </FieldRow>
              <FieldRow label="Password">
                <Input type="password" value={form.telnet_ssh.password} onChange={(e) => setNested('telnet_ssh', 'password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Confirm Password">
                <Input type="password" value={form.telnet_ssh.confirm_password} onChange={(e) => setNested('telnet_ssh', 'confirm_password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Enable Password">
                <Input type="password" value={form.telnet_ssh.enable_password} onChange={(e) => setNested('telnet_ssh', 'enable_password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Confirm Enable Password">
                <Input type="password" value={form.telnet_ssh.confirm_enable_password} onChange={(e) => setNested('telnet_ssh', 'confirm_enable_password', e.target.value)} />
              </FieldRow>
              <p className="mt-3 text-xs text-gray-500">
                <span className="text-red-500">*</span> Note: Not providing Telnet/SSH credentials may result in partial collection of inventory data.
              </p>
            </section>
          )}

          {tab === 'http' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">HTTP/HTTPS Parameters</h3>
              <FieldRow label="Protocol">
                <Select
                  value={form.http.protocol}
                  onChange={(e) => setNested('http', 'protocol', e.target.value as HttpParams['protocol'])}
                  options={[{ value: 'http', label: 'http' }, { value: 'https', label: 'https' }]}
                />
              </FieldRow>
              <FieldRow label="TCP Port (default is 80)" required>
                <Input type="number" value={form.http.tcp_port} onChange={(e) => setNested('http', 'tcp_port', Number(e.target.value))} />
              </FieldRow>
              <FieldRow label="Username">
                <Input value={form.http.username} onChange={(e) => setNested('http', 'username', e.target.value)} />
              </FieldRow>
              <FieldRow label="Password">
                <Input type="password" value={form.http.password} onChange={(e) => setNested('http', 'password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Confirm Password">
                <Input type="password" value={form.http.confirm_password} onChange={(e) => setNested('http', 'confirm_password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Monitor Username">
                <Input value={form.http.monitor_username} onChange={(e) => setNested('http', 'monitor_username', e.target.value)} />
              </FieldRow>
              <FieldRow label="Monitor Password">
                <Input type="password" value={form.http.monitor_password} onChange={(e) => setNested('http', 'monitor_password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Confirm Monitor Password">
                <Input type="password" value={form.http.confirm_monitor_password} onChange={(e) => setNested('http', 'confirm_monitor_password', e.target.value)} />
              </FieldRow>
            </section>
          )}

          {tab === 'tl1' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">TL1 Parameters</h3>
              <FieldRow label="Protocol">
                <Select
                  value={form.tl1.protocol}
                  onChange={(e) => setNested('tl1', 'protocol', e.target.value as Tl1Params['protocol'])}
                  options={[{ value: 'telnet', label: 'Telnet' }, { value: 'ssh', label: 'SSH' }]}
                />
              </FieldRow>
              <FieldRow label="Single Session TL1">
                <Select
                  value={form.tl1.single_session}
                  onChange={(e) => setNested('tl1', 'single_session', e.target.value as Tl1Params['single_session'])}
                  options={[{ value: 'disabled', label: 'disabled' }, { value: 'enabled', label: 'enabled' }]}
                />
              </FieldRow>
              <FieldRow label="Primary Proxy IP Address">
                <Input value={form.tl1.primary_proxy_ip} onChange={(e) => setNested('tl1', 'primary_proxy_ip', e.target.value)} />
              </FieldRow>
              <FieldRow label="Secondary Proxy IP Address">
                <Input value={form.tl1.secondary_proxy_ip} onChange={(e) => setNested('tl1', 'secondary_proxy_ip', e.target.value)} />
              </FieldRow>
              <FieldRow label="Username">
                <Input value={form.tl1.username} onChange={(e) => setNested('tl1', 'username', e.target.value)} />
              </FieldRow>
              <FieldRow label="Password">
                <Input type="password" value={form.tl1.password} onChange={(e) => setNested('tl1', 'password', e.target.value)} />
              </FieldRow>
              <FieldRow label="Confirm Password">
                <Input type="password" value={form.tl1.confirm_password} onChange={(e) => setNested('tl1', 'confirm_password', e.target.value)} />
              </FieldRow>
            </section>
          )}

          {tab === 'civic' && (
            <section className="space-y-2">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">Civic Location Parameters</h3>
              <FieldRow label="Region">
                <Select value={form.civic_location.region} onChange={(e) => setNested('civic_location', 'region', e.target.value)} options={REGION_OPTIONS} />
              </FieldRow>
              <FieldRow label="Country"><Input value={form.civic_location.country} onChange={(e) => setNested('civic_location', 'country', e.target.value)} /></FieldRow>
              <FieldRow label="State"><Input value={form.civic_location.state} onChange={(e) => setNested('civic_location', 'state', e.target.value)} /></FieldRow>
              <FieldRow label="City"><Input value={form.civic_location.city} onChange={(e) => setNested('civic_location', 'city', e.target.value)} /></FieldRow>
              <FieldRow label="County"><Input value={form.civic_location.county} onChange={(e) => setNested('civic_location', 'county', e.target.value)} /></FieldRow>
              <FieldRow label="Street"><Input value={form.civic_location.street} onChange={(e) => setNested('civic_location', 'street', e.target.value)} /></FieldRow>
              <FieldRow label="Building"><Input value={form.civic_location.building} onChange={(e) => setNested('civic_location', 'building', e.target.value)} /></FieldRow>
              <FieldRow label="Floor"><Input value={form.civic_location.floor} onChange={(e) => setNested('civic_location', 'floor', e.target.value)} /></FieldRow>
              <FieldRow label="Room"><Input value={form.civic_location.room} onChange={(e) => setNested('civic_location', 'room', e.target.value)} /></FieldRow>
              <FieldRow label="Longitude" hint="(deg)"><Input value={form.civic_location.longitude} onChange={(e) => setNested('civic_location', 'longitude', e.target.value)} /></FieldRow>
              <FieldRow label="Latitude" hint="(deg)"><Input value={form.civic_location.latitude} onChange={(e) => setNested('civic_location', 'latitude', e.target.value)} /></FieldRow>
            </section>
          )}

          {tab === 'udf' && (
            <section className="space-y-3">
              <h3 className="mb-3 text-center text-sm font-semibold text-gray-900 dark:text-gray-100">User Defined Fields</h3>
              {form.user_defined_fields.length === 0 && (
                <p className="text-center text-sm text-gray-500">No custom fields. Click "Add field" to create one.</p>
              )}
              {form.user_defined_fields.map((udf, i) => (
                <div key={i} className="flex gap-2">
                  <Input
                    placeholder="Key"
                    value={udf.key}
                    onChange={(e) => {
                      const next = [...form.user_defined_fields];
                      next[i] = { ...next[i], key: e.target.value };
                      set('user_defined_fields', next);
                    }}
                  />
                  <Input
                    placeholder="Value"
                    value={udf.value}
                    onChange={(e) => {
                      const next = [...form.user_defined_fields];
                      next[i] = { ...next[i], value: e.target.value };
                      set('user_defined_fields', next);
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => set('user_defined_fields', form.user_defined_fields.filter((_, j) => j !== i))}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => set('user_defined_fields', [...form.user_defined_fields, { key: '', value: '' }])}
              >
                + Add field
              </Button>
            </section>
          )}
        </div>
      </form>

      <div className="mt-6 flex justify-end gap-2 border-t border-gray-200 pt-4 dark:border-gray-700">
        <Button type="button" onClick={(e) => handleSubmit(e as unknown as React.FormEvent)} disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving...' : device ? 'Save' : 'Add'}
        </Button>
        <Button type="button" variant="ghost" onClick={() => verifyMutation.mutate()} disabled={verifyMutation.isPending}>
          {verifyMutation.isPending ? 'Verifying...' : 'Verify Credentials'}
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </Modal>
  );
}
