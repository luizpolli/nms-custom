import { useEffect, useMemo, useState } from 'react';
import { Check, Pencil, Plus, Send, Trash2, X } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Card, CardHeader, Input, Modal, Select, pushToast } from '../../components/ui';
import { api } from '../../lib/api';

type ForwardingProtocol = 'syslog_udp' | 'syslog_tcp' | 'snmp_trap' | 'http_webhook';
type EventType = 'trap' | 'syslog' | 'telemetry' | 'alarm';
type Severity = 'critical' | 'major' | 'minor' | 'warning' | 'info';

interface ForwardingTarget {
  id: string;
  name: string;
  protocol: ForwardingProtocol;
  target_host: string;
  target_port: number;
  event_types: EventType[];
  severity_filter?: Severity | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface TestResult {
  ok: boolean;
  message: string;
}

type FormState = {
  name: string;
  protocol: ForwardingProtocol;
  target_host: string;
  target_port: number;
  event_types: EventType[];
  severity_filter: Severity | '';
  enabled: boolean;
};

const EVENT_TYPES: Array<{ value: EventType; label: string }> = [
  { value: 'trap', label: 'Traps' },
  { value: 'syslog', label: 'Syslogs' },
  { value: 'telemetry', label: 'Telemetry' },
  { value: 'alarm', label: 'Alarms' },
];

const PROTOCOLS: Array<{ value: ForwardingProtocol; label: string; defaultPort: number }> = [
  { value: 'syslog_udp', label: 'Syslog UDP', defaultPort: 514 },
  { value: 'syslog_tcp', label: 'Syslog TCP', defaultPort: 514 },
  { value: 'snmp_trap', label: 'SNMP Trap', defaultPort: 162 },
  { value: 'http_webhook', label: 'HTTP Webhook', defaultPort: 80 },
];

const EMPTY_FORM: FormState = {
  name: '',
  protocol: 'syslog_udp',
  target_host: '',
  target_port: 514,
  event_types: ['trap', 'syslog', 'alarm'],
  severity_filter: '',
  enabled: true,
};

function protocolLabel(protocol: ForwardingProtocol) {
  return PROTOCOLS.find((item) => item.value === protocol)?.label ?? protocol;
}

function toForm(target: ForwardingTarget | null): FormState {
  if (!target) return EMPTY_FORM;
  return {
    name: target.name,
    protocol: target.protocol,
    target_host: target.target_host,
    target_port: target.target_port,
    event_types: target.event_types,
    severity_filter: target.severity_filter ?? '',
    enabled: target.enabled,
  };
}

export function ForwardingSettings() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ForwardingTarget | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const targetsQuery = useQuery({
    queryKey: ['forwarding-targets'],
    queryFn: () => api.get<ForwardingTarget[]>('/forwarding/targets').then((r) => r.data),
  });

  useEffect(() => setForm(toForm(editing)), [editing]);

  const targets = useMemo(() => targetsQuery.data ?? [], [targetsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        ...form,
        name: form.name.trim(),
        target_host: form.target_host.trim(),
        severity_filter: form.severity_filter || null,
      };
      return editing
        ? api.patch<ForwardingTarget>(`/forwarding/targets/${editing.id}`, payload)
        : api.post<ForwardingTarget>('/forwarding/targets', payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['forwarding-targets'] });
      setModalOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      pushToast('Forwarding target saved', 'success');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/forwarding/targets/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['forwarding-targets'] });
      pushToast('Forwarding target deleted', 'success');
    },
  });

  const toggleMutation = useMutation({
    mutationFn: (target: ForwardingTarget) => api.patch(`/forwarding/targets/${target.id}`, { enabled: !target.enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['forwarding-targets'] }),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => api.post<TestResult>(`/forwarding/targets/${id}/test`).then((r) => r.data),
    onSuccess: (result) => pushToast(result.message, result.ok ? 'success' : 'error'),
  });

  function openCreate() {
    setEditing(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  }

  function openEdit(target: ForwardingTarget) {
    setEditing(target);
    setModalOpen(true);
  }

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleEventType(type: EventType) {
    setForm((prev) => {
      const current = new Set(prev.event_types);
      if (current.has(type)) current.delete(type);
      else current.add(type);
      return { ...prev, event_types: Array.from(current) as EventType[] };
    });
  }

  function setProtocol(protocol: ForwardingProtocol) {
    const defaultPort = PROTOCOLS.find((item) => item.value === protocol)?.defaultPort ?? form.target_port;
    setForm((prev) => ({ ...prev, protocol, target_port: defaultPort }));
  }

  const canSave = form.name.trim() && form.target_host.trim() && form.target_port >= 1 && form.target_port <= 65535 && form.event_types.length > 0;

  return (
    <div className="space-y-6">
      <Card padding={false}>
        <CardHeader
          title={
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Event Forwarding Targets</h2>
                <p className="mt-1 text-xs font-normal text-gray-500">Relay traps, syslogs, telemetry, and alarm events to upstream collectors.</p>
              </div>
              <Button size="sm" onClick={openCreate} leftIcon={<Plus className="h-4 w-4" />}>Add Target</Button>
            </div>
          }
        />

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-xs uppercase text-gray-500 dark:bg-gray-800 dark:text-gray-400">
              <tr>
                {['Name', 'Protocol', 'Destination', 'Events', 'Severity', 'Status', 'Actions'].map((h) => (
                  <th key={h} className="px-4 py-3 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
              {targets.map((target) => (
                <tr key={target.id}>
                  <td className="px-4 py-3 font-medium text-gray-900 dark:text-gray-100">{target.name}</td>
                  <td className="px-4 py-3">{protocolLabel(target.protocol)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{target.target_host}:{target.target_port}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {target.event_types.map((type) => <Badge key={type} variant="default">{type}</Badge>)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {target.severity_filter ? <Badge variant={target.severity_filter}>{target.severity_filter}</Badge> : <span className="text-gray-500">All</span>}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => toggleMutation.mutate(target)}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
                        target.enabled ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                      }`}
                    >
                      {target.enabled ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
                      {target.enabled ? 'Enabled' : 'Disabled'}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <Button size="xs" variant="outline" onClick={() => testMutation.mutate(target.id)} leftIcon={<Send className="h-3.5 w-3.5" />}>Test</Button>
                      <Button size="xs" variant="ghost" onClick={() => openEdit(target)} leftIcon={<Pencil className="h-3.5 w-3.5" />}>Edit</Button>
                      <Button size="xs" variant="danger" onClick={() => deleteMutation.mutate(target.id)} leftIcon={<Trash2 className="h-3.5 w-3.5" />}>Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
              {!targets.length && (
                <tr>
                  <td className="px-4 py-6 text-gray-500" colSpan={7}>
                    No forwarding targets configured.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={editing ? 'Edit Forwarding Target' : 'Add Forwarding Target'} size="lg">
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="mb-1 block font-medium">Name</span>
            <Input value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Upstream collector" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Protocol</span>
            <Select value={form.protocol} onChange={(e) => setProtocol(e.target.value as ForwardingProtocol)}>
              {PROTOCOLS.map((protocol) => <option key={protocol.value} value={protocol.value}>{protocol.label}</option>)}
            </Select>
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Target host</span>
            <Input value={form.target_host} onChange={(e) => set('target_host', e.target.value)} placeholder="192.0.2.10" />
          </label>
          <label className="block">
            <span className="mb-1 block font-medium">Target port</span>
            <Input type="number" min={1} max={65535} value={form.target_port} onChange={(e) => set('target_port', Number(e.target.value))} />
          </label>
          <fieldset className="md:col-span-2">
            <legend className="mb-2 font-medium">Event types</legend>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {EVENT_TYPES.map((type) => (
                <label key={type.value} className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 dark:border-gray-700">
                  <input type="checkbox" checked={form.event_types.includes(type.value)} onChange={() => toggleEventType(type.value)} />
                  {type.label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block">
            <span className="mb-1 block font-medium">Minimum severity</span>
            <Select value={form.severity_filter} onChange={(e) => set('severity_filter', e.target.value as FormState['severity_filter'])}>
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="major">Major</option>
              <option value="minor">Minor</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </Select>
          </label>
          <label className="flex items-center gap-2 md:pt-6">
            <input type="checkbox" checked={form.enabled} onChange={(e) => set('enabled', e.target.checked)} />
            Enabled
          </label>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
          <Button onClick={() => saveMutation.mutate()} disabled={!canSave || saveMutation.isPending} loading={saveMutation.isPending}>
            {editing ? 'Save Changes' : 'Create Target'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
