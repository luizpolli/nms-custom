import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Play, Trash2 } from 'lucide-react';
import { Card, Button, EmptyState, Input, PageHeader, Select } from '../../components/ui';
import { api } from '../../lib/api';

type PolicyType = 'device_health' | 'interface_health' | 'custom_mib' | 'optical_sfp' | 'optical_15m' | 'optical_1d' | 'mpls_link_performance' | 'ip_sla' | 'gnss' | 'syslog';

interface MonitoringPolicy {
  id: string;
  name: string;
  description?: string | null;
  policy_type: PolicyType;
  enabled: boolean;
  interval_seconds: number;
  target_all_devices: boolean;
  device_ids: string[];
  metric_oids: Array<{ name?: string; oid: string; unit?: string }>;
  thresholds: Record<string, unknown>;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_status?: string | null;
  last_error?: string | null;
}

interface Preset {
  name: string;
  policy_type: PolicyType;
  interval_seconds: number;
  description: string;
}

type FormState = Omit<MonitoringPolicy, 'id' | 'last_run_at' | 'next_run_at' | 'last_status' | 'last_error' | 'thresholds'> & { oidText: string };

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  policy_type: 'device_health',
  enabled: true,
  interval_seconds: 300,
  target_all_devices: true,
  device_ids: [],
  metric_oids: [],
  oidText: '',
};

const intervals = [
  { value: '60', label: '1 minute' },
  { value: '300', label: '5 minutes' },
  { value: '900', label: '15 minutes' },
  { value: '3600', label: '1 hour' },
  { value: '21600', label: '6 hours' },
  { value: '43200', label: '12 hours' },
  { value: '86400', label: '24 hours' },
];

const policyTypes = [
  { value: 'device_health', label: 'Device Health' },
  { value: 'interface_health', label: 'Interface Health' },
  { value: 'custom_mib', label: 'Custom MIB Polling' },
  { value: 'optical_sfp', label: 'Optical SFP' },
  { value: 'optical_15m', label: 'Optical 15 mins' },
  { value: 'optical_1d', label: 'Optical 1 day' },
  { value: 'mpls_link_performance', label: 'MPLS Link Performance' },
  { value: 'ip_sla', label: 'IP SLA' },
  { value: 'gnss', label: 'GNSS' },
  { value: 'syslog', label: 'Syslog Monitoring' },
];

function oidTextToMetrics(text: string) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, oid, unit] = line.split(',').map((part) => part.trim());
      return oid ? { name, oid, unit } : { oid: name };
    });
}

function metricsToOidText(metrics: FormState['metric_oids']) {
  return metrics.map((m) => [m.name, m.oid, m.unit].filter(Boolean).join(', ')).join('\n');
}

function formatInterval(seconds: number) {
  return intervals.find((i) => Number(i.value) === seconds)?.label ?? `${seconds}s`;
}

export function MonitoringPoliciesPage() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const queryString = searchParams.toString();
  const [editing, setEditing] = useState<MonitoringPolicy | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const chassisParams = new URLSearchParams(queryString);
  const chassisInterface = chassisParams.get('interface') ?? '';
  const chassisDeviceId = chassisParams.get('device_id') ?? '';

  const policiesQuery = useQuery({
    queryKey: ['monitoring-policies'],
    queryFn: () => api.get<MonitoringPolicy[]>('/monitoring-policies').then((r) => r.data),
  });
  const presetsQuery = useQuery({
    queryKey: ['monitoring-policy-presets'],
    queryFn: () => api.get<Preset[]>('/monitoring-policies/presets').then((r) => r.data),
  });

  useEffect(() => {
    if (!editing) {
      setForm(EMPTY_FORM);
      return;
    }
    setForm({
      name: editing.name,
      description: editing.description ?? '',
      policy_type: editing.policy_type,
      enabled: editing.enabled,
      interval_seconds: editing.interval_seconds,
      target_all_devices: editing.target_all_devices,
      device_ids: editing.device_ids ?? [],
      metric_oids: editing.metric_oids ?? [],
      oidText: metricsToOidText(editing.metric_oids ?? []),
    });
  }, [editing]);

  useEffect(() => {
    if (!chassisInterface && !chassisDeviceId) return;
    if (editing) return;
    const targetName = chassisInterface || 'selected interface';
    setForm((prev) => ({
      ...prev,
      name: prev.name || `Interface health - ${targetName}`,
      description: prev.description || `Created from Chassis View context for ${targetName}.`,
      policy_type: 'interface_health',
      target_all_devices: !chassisDeviceId,
      device_ids: chassisDeviceId ? [chassisDeviceId] : [],
    }));
  }, [chassisDeviceId, chassisInterface, editing]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        name: form.name,
        description: form.description?.trim() || null,
        policy_type: form.policy_type,
        enabled: form.enabled,
        interval_seconds: form.interval_seconds,
        target_all_devices: form.target_all_devices,
        device_ids: form.device_ids,
        metric_oids: oidTextToMetrics(form.oidText),
        thresholds: {},
      };
      return editing ? api.patch(`/monitoring-policies/${editing.id}`, payload) : api.post('/monitoring-policies', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['monitoring-policies'] });
      setEditing(null);
      setForm(EMPTY_FORM);
    },
  });

  const runMutation = useMutation({
    mutationFn: (id: string) => api.post(`/monitoring-policies/${id}/run`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitoring-policies'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/monitoring-policies/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['monitoring-policies'] }),
  });

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function applyPreset(preset: Preset) {
    setForm((prev) => ({
      ...prev,
      name: preset.name,
      description: preset.description,
      policy_type: preset.policy_type,
      interval_seconds: preset.interval_seconds,
    }));
  }

  const policies = policiesQuery.data ?? [];

  return (
    <div className="space-y-6 p-6">
      <PageHeader title="Monitoring Policies" subtitle="EPNM-style polling policies for all devices, custom MIBs, syslogs, and reports" />

      <Card className="p-4">
        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{editing ? `Edit ${editing.name}` : 'New policy'}</h2>
            <p className="text-xs text-gray-500">Supported cadences: 1m, 5m, 15m, 1h, 6h, 12h, 24h. Default policies target all devices.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(presetsQuery.data ?? []).slice(0, 5).map((preset) => (
              <Button key={preset.name} variant="ghost" onClick={() => applyPreset(preset)}>{preset.name}</Button>
            ))}
            {editing && <Button variant="ghost" onClick={() => setEditing(null)}>Cancel edit</Button>}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Input label="Name" value={form.name} onChange={(e) => set('name', e.target.value)} required />
          <Select label="Policy type" value={form.policy_type} onChange={(e) => set('policy_type', e.target.value as PolicyType)} options={policyTypes} />
          <Select label="Polling interval" value={String(form.interval_seconds)} onChange={(e) => set('interval_seconds', Number(e.target.value))} options={intervals} />
          <label className="flex items-center gap-2 pt-6 text-sm text-gray-700 dark:text-gray-300">
            <input type="checkbox" checked={form.enabled} onChange={(e) => set('enabled', e.target.checked)} /> Enabled
          </label>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-[16rem_1fr]">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={form.target_all_devices}
              onChange={(e) => set('target_all_devices', e.target.checked)}
            />
            Target all devices
          </label>
          <Input
            label="Target device IDs"
            value={form.device_ids.join(', ')}
            onChange={(e) => set('device_ids', e.target.value.split(',').map((item) => item.trim()).filter(Boolean))}
            disabled={form.target_all_devices}
            hint={chassisInterface ? `Chassis context: ${chassisInterface}` : undefined}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">Description</label>
            <textarea value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} className="min-h-24 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100" />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">Custom MIB OIDs</label>
            <textarea value={form.oidText} onChange={(e) => set('oidText', e.target.value)} placeholder="cpuTemp, 1.3.6.1.4.1..., C\nopticalTxPower, 1.3.6.1.4.1..., dBm" className="min-h-24 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-mono text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100" />
            <p className="mt-1 text-xs text-gray-500">One per line: name, oid, unit. Used when policy type is Custom MIB.</p>
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <Button onClick={() => saveMutation.mutate()} disabled={!form.name.trim() || saveMutation.isPending}>{saveMutation.isPending ? 'Saving…' : editing ? 'Save changes' : 'Create policy'}</Button>
        </div>
      </Card>

      <Card className="p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Configured policies</h2>
        {policiesQuery.isLoading && <p className="py-6 text-center text-sm text-gray-400">Loading policies…</p>}
        {!policiesQuery.isLoading && policies.length === 0 && <EmptyState title="No monitoring policies" description="Create or use a preset to start collecting device information." />}
        {policies.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {['Name', 'Type', 'Interval', 'Target', 'Last run', 'Next run', 'Status', 'Actions'].map((h) => <th key={h} className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>)}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {policies.map((policy) => (
                  <tr key={policy.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                    <td className="px-4 py-2 font-medium">{policy.name}</td>
                    <td className="px-4 py-2">{policy.policy_type}</td>
                    <td className="px-4 py-2">{formatInterval(policy.interval_seconds)}</td>
                    <td className="px-4 py-2">{policy.target_all_devices ? 'All devices' : `${policy.device_ids?.length ?? 0} devices`}</td>
                    <td className="px-4 py-2 text-xs">{policy.last_run_at ? new Date(policy.last_run_at).toLocaleString() : '—'}</td>
                    <td className="px-4 py-2 text-xs">{policy.next_run_at ? new Date(policy.next_run_at).toLocaleString() : '—'}</td>
                    <td className="px-4 py-2">{policy.enabled ? (policy.last_status ?? 'enabled') : 'disabled'}</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          title="Edit"
                          aria-label="Edit policy"
                          className="rounded p-1.5 text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                          onClick={() => setEditing(policy)}
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          title="Run now"
                          aria-label="Run policy now"
                          className="rounded p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 disabled:opacity-50"
                          onClick={() => runMutation.mutate(policy.id)}
                          disabled={runMutation.isPending}
                        >
                          <Play className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          title="Delete"
                          aria-label="Delete policy"
                          className="rounded p-1.5 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30"
                          onClick={() => deleteMutation.mutate(policy.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
