import { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { Modal, Button, Input, Select } from '../../components/ui';

interface Credential {
  id: string;
  name: string;
  hostname: string;
  username: string;
  protocol: string;
  snmp_version: string;
  port: number;
  has_secret: boolean;
  metadata?: Partial<CredentialFormData>;
}

interface CredentialFormData {
  // General
  profile_name: string;
  description: string;
  // SNMP
  snmp_version: 'v1' | 'v2c' | 'v3';
  snmp_retries: number;
  snmp_timeout: number;
  snmp_port: number;
  read_community: string;
  confirm_read_community: string;
  write_community: string;
  confirm_write_community: string;
  // Telnet/SSH
  telnet_protocol: 'telnet' | 'ssh2' | 'netconf-ssh2';
  telnet_port: number;
  telnet_timeout: number;
  telnet_username: string;
  telnet_password: string;
  telnet_confirm_password: string;
  telnet_enable_password: string;
  telnet_confirm_enable_password: string;
  // HTTP
  http_protocol: 'http' | 'https';
  http_tcp_port: number;
  http_username: string;
  http_password: string;
  http_confirm_password: string;
  http_monitor_username: string;
  http_monitor_password: string;
  http_confirm_monitor_password: string;
  // TL1
  tl1_enable_ssh: boolean;
  tl1_single_session: boolean;
  tl1_username: string;
  tl1_password: string;
  tl1_confirm_password: string;
  tl1_primary_proxy_ip: string;
  tl1_secondary_proxy_ip: string;
}

interface CredentialFormModalProps {
  open: boolean;
  onClose: () => void;
  credential?: Credential | null;
}

const EMPTY_FORM: CredentialFormData = {
  profile_name: '',
  description: '',
  snmp_version: 'v2c',
  snmp_retries: 2,
  snmp_timeout: 10,
  snmp_port: 161,
  read_community: '',
  confirm_read_community: '',
  write_community: '',
  confirm_write_community: '',
  telnet_protocol: 'telnet',
  telnet_port: 23,
  telnet_timeout: 60,
  telnet_username: '',
  telnet_password: '',
  telnet_confirm_password: '',
  telnet_enable_password: '',
  telnet_confirm_enable_password: '',
  http_protocol: 'http',
  http_tcp_port: 80,
  http_username: '',
  http_password: '',
  http_confirm_password: '',
  http_monitor_username: '',
  http_monitor_password: '',
  http_confirm_monitor_password: '',
  tl1_enable_ssh: false,
  tl1_single_session: false,
  tl1_username: '',
  tl1_password: '',
  tl1_confirm_password: '',
  tl1_primary_proxy_ip: '',
  tl1_secondary_proxy_ip: '',
};

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border-b border-gray-200 dark:border-gray-700 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-2 py-2 text-left text-sm font-semibold text-gray-900 dark:text-gray-100 hover:bg-gray-50 dark:hover:bg-gray-800"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {title}
      </button>
      {open && <div className="px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-2">{children}</div>}
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-12 items-center gap-2">
      <label className="col-span-5 text-right text-sm text-gray-700 dark:text-gray-300">
        {required && <span className="text-red-500 mr-0.5">*</span>}
        {label}
      </label>
      <div className="col-span-7">{children}</div>
    </div>
  );
}

export function CredentialFormModal({ open, onClose, credential }: CredentialFormModalProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<CredentialFormData>(EMPTY_FORM);

  useEffect(() => {
    if (!open) return;
    if (credential) {
      setForm({
        ...EMPTY_FORM,
        ...credential.metadata,
        profile_name: credential.name,
      } as CredentialFormData);
    } else {
      setForm(EMPTY_FORM);
    }
  }, [credential, open]);

  const mutation = useMutation({
    mutationFn: (data: CredentialFormData) => {
      const hasSnmp = !!data.read_community;
      const hasSsh = !!data.telnet_password;
      const hasHttp = !!data.http_password;
      if (!hasSnmp && !hasSsh && !hasHttp) {
        return Promise.reject(new Error('Provide at least one credential set: SNMP Read Community, Telnet/SSH Password, or HTTP Password.'));
      }
      const payload = {
        name: data.profile_name,
        hostname: '',
        username: data.telnet_username || data.http_username || data.tl1_username,
        secret: data.telnet_password || data.http_password || data.read_community,
        protocol: hasSsh ? 'ssh' : 'snmp',
        snmp_version: data.snmp_version,
        port: hasSsh ? data.telnet_port : data.snmp_port,
        metadata: data,
      };
      if (credential) {
        const p = { ...payload };
        if (!p.secret) delete (p as Partial<typeof p>).secret;
        return api.patch(`/credentials/${credential.id}`, p);
      }
      return api.post('/credentials', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['credentials'] });
      onClose();
    },
    onError: (err: Error) => {
      console.error('Save credential failed', err);
      alert(err.message || 'Failed to save credential profile');
    },
  });

  const set = <K extends keyof CredentialFormData>(key: K, value: CredentialFormData[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <Modal open={open} onClose={onClose} title={credential ? 'Edit Credential Profile' : 'Add Credential Profile'} size="3xl">
      <form onSubmit={handleSubmit} className="space-y-2">
        <p className="text-xs text-gray-600 dark:text-gray-400">
          Entering a valid value in either SNMP Read Community, or Protocol Username and Password in Telnet/SSH Parameters,
          or Protocol Username and Password in HTTP Parameter is required. <span className="text-red-500">*</span>Indicates required fields
        </p>

        <Section title="General Parameters">
          <Field label="Profile Name" required>
            <Input value={form.profile_name} onChange={(e) => set('profile_name', e.target.value)} required />
          </Field>
          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              rows={3}
              className="w-full rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
            />
          </Field>
        </Section>

        <Section title="SNMP Parameters">
          <Field label="Version">
            <Select
              value={form.snmp_version}
              onChange={(e) => set('snmp_version', e.target.value as CredentialFormData['snmp_version'])}
              options={[{ value: 'v1', label: 'v1' }, { value: 'v2c', label: 'v2c' }, { value: 'v3', label: 'v3' }]}
            />
          </Field>
          <Field label="Retries" required>
            <Input type="number" value={form.snmp_retries} onChange={(e) => set('snmp_retries', Number(e.target.value))} />
          </Field>
          <Field label="Timeout (secs)" required>
            <Input type="number" value={form.snmp_timeout} onChange={(e) => set('snmp_timeout', Number(e.target.value))} />
          </Field>
          <Field label="SNMP Port" required>
            <Input type="number" value={form.snmp_port} onChange={(e) => set('snmp_port', Number(e.target.value))} />
          </Field>
          <Field label="Read Community" required>
            <Input type="password" value={form.read_community} onChange={(e) => set('read_community', e.target.value)} />
          </Field>
          <Field label="Confirm Read Community" required>
            <Input type="password" value={form.confirm_read_community} onChange={(e) => set('confirm_read_community', e.target.value)} />
          </Field>
          <Field label="Write Community">
            <Input type="password" value={form.write_community} onChange={(e) => set('write_community', e.target.value)} />
          </Field>
          <Field label="Confirm Write Community">
            <Input type="password" value={form.confirm_write_community} onChange={(e) => set('confirm_write_community', e.target.value)} />
          </Field>
        </Section>

        <Section title="Telnet/SSH Parameters" defaultOpen={false}>
          <Field label="Protocol">
            <Select
              value={form.telnet_protocol}
              onChange={(e) => set('telnet_protocol', e.target.value as CredentialFormData['telnet_protocol'])}
              options={[
                { value: 'telnet', label: 'Telnet' },
                { value: 'ssh2', label: 'SSH2' },
                { value: 'netconf-ssh2', label: 'Netconf Over SSH2' },
              ]}
            />
          </Field>
          <Field label="Port" required>
            <Input type="number" value={form.telnet_port} onChange={(e) => set('telnet_port', Number(e.target.value))} />
          </Field>
          <Field label="Timeout (secs)" required>
            <Input type="number" value={form.telnet_timeout} onChange={(e) => set('telnet_timeout', Number(e.target.value))} />
          </Field>
          <div />
          <Field label="Username">
            <Input value={form.telnet_username} onChange={(e) => set('telnet_username', e.target.value)} />
          </Field>
          <Field label="Confirm Password">
            <Input type="password" value={form.telnet_confirm_password} onChange={(e) => set('telnet_confirm_password', e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" value={form.telnet_password} onChange={(e) => set('telnet_password', e.target.value)} />
          </Field>
          <Field label="Confirm Enable Password">
            <Input type="password" value={form.telnet_confirm_enable_password} onChange={(e) => set('telnet_confirm_enable_password', e.target.value)} />
          </Field>
          <Field label="Enable Password">
            <Input type="password" value={form.telnet_enable_password} onChange={(e) => set('telnet_enable_password', e.target.value)} />
          </Field>
        </Section>

        <Section title="HTTP Parameters" defaultOpen={false}>
          <Field label="Protocol">
            <Select
              value={form.http_protocol}
              onChange={(e) => set('http_protocol', e.target.value as CredentialFormData['http_protocol'])}
              options={[{ value: 'http', label: 'http' }, { value: 'https', label: 'https' }]}
            />
          </Field>
          <Field label="TCP Port" required>
            <Input type="number" value={form.http_tcp_port} onChange={(e) => set('http_tcp_port', Number(e.target.value))} />
          </Field>
          <Field label="Username">
            <Input value={form.http_username} onChange={(e) => set('http_username', e.target.value)} />
          </Field>
          <Field label="Confirm Password">
            <Input type="password" value={form.http_confirm_password} onChange={(e) => set('http_confirm_password', e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" value={form.http_password} onChange={(e) => set('http_password', e.target.value)} />
          </Field>
          <Field label="Confirm Monitor Password">
            <Input type="password" value={form.http_confirm_monitor_password} onChange={(e) => set('http_confirm_monitor_password', e.target.value)} />
          </Field>
          <Field label="Monitor Username">
            <Input value={form.http_monitor_username} onChange={(e) => set('http_monitor_username', e.target.value)} />
          </Field>
          <Field label="Monitor Password">
            <Input type="password" value={form.http_monitor_password} onChange={(e) => set('http_monitor_password', e.target.value)} />
          </Field>
        </Section>

        <Section title="TL1 Parameters" defaultOpen={false}>
          <Field label="Enable SSH for TL1">
            <input type="checkbox" checked={form.tl1_enable_ssh} onChange={(e) => set('tl1_enable_ssh', e.target.checked)} />
          </Field>
          <Field label="Enable Single Session TL1">
            <input type="checkbox" checked={form.tl1_single_session} onChange={(e) => set('tl1_single_session', e.target.checked)} />
          </Field>
          <Field label="Username">
            <Input value={form.tl1_username} onChange={(e) => set('tl1_username', e.target.value)} />
          </Field>
          <Field label="Confirm Password">
            <Input type="password" value={form.tl1_confirm_password} onChange={(e) => set('tl1_confirm_password', e.target.value)} />
          </Field>
          <Field label="Password">
            <Input type="password" value={form.tl1_password} onChange={(e) => set('tl1_password', e.target.value)} />
          </Field>
          <Field label="Secondary Proxy IP Address">
            <Input value={form.tl1_secondary_proxy_ip} onChange={(e) => set('tl1_secondary_proxy_ip', e.target.value)} />
          </Field>
          <Field label="Primary Proxy IP Address">
            <Input value={form.tl1_primary_proxy_ip} onChange={(e) => set('tl1_primary_proxy_ip', e.target.value)} />
          </Field>
        </Section>

        <div className="flex justify-end gap-2 border-t border-gray-200 dark:border-gray-700 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
