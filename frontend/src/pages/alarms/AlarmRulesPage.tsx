import { Fragment, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GitBranch, ListChecks, SlidersHorizontal, TableProperties } from 'lucide-react';
import { PageHeader, Card, Button, Input, Select, EmptyState, InfoFloat, PageIntroFloat } from '../../components/ui';
import { api } from '../../lib/api';

type SourceType = 'snmp_trap' | 'syslog' | 'event' | 'any';
type MatchField = 'trap_oid' | 'event_type' | 'message' | 'source_host' | 'category';
type MatchOperator = 'equals' | 'starts_with' | 'contains' | 'regex';
type RuleSeverity = 'critical' | 'major' | 'minor' | 'warning' | 'info' | 'clear';

interface AlarmRule {
  id: string;
  name: string;
  description?: string | null;
  enabled: boolean;
  priority: number;
  source_type: SourceType;
  match_field: MatchField;
  match_operator: MatchOperator;
  match_pattern: string;
  severity: RuleSeverity;
  category?: string | null;
  event_type?: string | null;
  message_template?: string | null;
  correlation_key_template?: string | null;
  auto_clear: boolean;
}

type AlarmRuleForm = Omit<AlarmRule, 'id'>;

const EMPTY_FORM: AlarmRuleForm = {
  name: '',
  description: '',
  enabled: true,
  priority: 100,
  source_type: 'snmp_trap',
  match_field: 'trap_oid',
  match_operator: 'equals',
  match_pattern: '',
  severity: 'info',
  category: '',
  event_type: '',
  message_template: '',
  correlation_key_template: '',
  auto_clear: false,
};

const sourceOptions = [
  { value: 'snmp_trap', label: 'SNMP Trap' },
  { value: 'syslog', label: 'Syslog' },
  { value: 'event', label: 'Event' },
  { value: 'any', label: 'Any' },
];

const matchFieldOptions = [
  { value: 'trap_oid', label: 'Trap OID' },
  { value: 'event_type', label: 'Event type' },
  { value: 'message', label: 'Message' },
  { value: 'source_host', label: 'Source host' },
  { value: 'category', label: 'Category' },
];

const operatorOptions = [
  { value: 'equals', label: 'Equals' },
  { value: 'starts_with', label: 'Starts with' },
  { value: 'contains', label: 'Contains' },
  { value: 'regex', label: 'Regex' },
];

const severityOptions = [
  { value: 'critical', label: 'Critical' },
  { value: 'major', label: 'Major' },
  { value: 'minor', label: 'Minor' },
  { value: 'warning', label: 'Warning' },
  { value: 'info', label: 'Info' },
  { value: 'clear', label: 'Clear' },
];

const ALARM_RULES_HELP = {
  overview: 'Alarm rules customize how traps, syslogs, and internal events become alarms. Use them to override severity, category, message text, correlation keys, and auto-clear behavior before events reach the alarm table.',
  form: 'Create or edit one matching rule. Lower priority numbers run first; the first enabled match wins.',
  list: 'Review configured rules in execution order. Edit or delete rules here when event normalization needs to change.',
};
const ALARM_RULES_INTRO_STORAGE_KEY = 'nms-alarm-rules-intro-dismissed-v2';

function AlarmRulesDiagram() {
  const nodes = [
    { icon: <GitBranch className="h-4 w-4 text-cisco-blue" />, title: 'Incoming event', text: 'Trap, syslog, or internal event payload.' },
    { icon: <SlidersHorizontal className="h-4 w-4 text-amber-500" />, title: 'Match rule', text: 'Source, field, operator, pattern, and priority.' },
    { icon: <ListChecks className="h-4 w-4 text-emerald-500" />, title: 'Normalize alarm', text: 'Apply severity, category, message, correlation, and auto-clear.' },
    { icon: <TableProperties className="h-4 w-4 text-indigo-500" />, title: 'Alarm views', text: 'Rules affect Alarms, Assurance, Services, and AI Ops evidence.' },
  ];

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-gray-950">
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] md:items-center">
        {nodes.map((node, index) => (
          <Fragment key={node.title}>
            <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
              <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                {node.icon}
                <span>{node.title}</span>
              </div>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{node.text}</p>
            </div>
            {index < nodes.length - 1 && (
              <div className="hidden text-center text-xl text-gray-400 md:block">-&gt;</div>
            )}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

async function fetchRules(): Promise<AlarmRule[]> {
  const { data } = await api.get<AlarmRule[]>('/alarm-rules');
  return data;
}

function normalizePayload(form: AlarmRuleForm) {
  return {
    ...form,
    description: form.description?.trim() || null,
    category: form.category?.trim() || null,
    event_type: form.event_type?.trim() || null,
    message_template: form.message_template?.trim() || null,
    correlation_key_template: form.correlation_key_template?.trim() || null,
  };
}

export function AlarmRulesPage({ embedded = false }: { embedded?: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<AlarmRule | null>(null);
  const [form, setForm] = useState<AlarmRuleForm>(EMPTY_FORM);
  const [showIntro, setShowIntro] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(ALARM_RULES_INTRO_STORAGE_KEY) !== 'true';
  });

  const rulesQuery = useQuery({ queryKey: ['alarm-rules'], queryFn: fetchRules });

  useEffect(() => {
    if (!editing) {
      setForm(EMPTY_FORM);
      return;
    }
    const rest = {
      name: editing.name,
      description: editing.description,
      enabled: editing.enabled,
      priority: editing.priority,
      source_type: editing.source_type,
      match_field: editing.match_field,
      match_operator: editing.match_operator,
      match_pattern: editing.match_pattern,
      severity: editing.severity,
      category: editing.category,
      event_type: editing.event_type,
      message_template: editing.message_template,
      correlation_key_template: editing.correlation_key_template,
      auto_clear: editing.auto_clear,
    };
    setForm({
      ...rest,
      description: rest.description ?? '',
      category: rest.category ?? '',
      event_type: rest.event_type ?? '',
      message_template: rest.message_template ?? '',
      correlation_key_template: rest.correlation_key_template ?? '',
    });
  }, [editing]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = normalizePayload(form);
      return editing
        ? api.patch(`/alarm-rules/${editing.id}`, payload)
        : api.post('/alarm-rules', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alarm-rules'] });
      setEditing(null);
      setForm(EMPTY_FORM);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/alarm-rules/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alarm-rules'] }),
  });

  function set<K extends keyof AlarmRuleForm>(key: K, value: AlarmRuleForm[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const rules = rulesQuery.data ?? [];

  return (
    <div className={embedded ? 'space-y-6' : 'space-y-6 p-6'}>
      {!embedded && showIntro && (
        <PageIntroFloat
          title="Alarm Rules guide"
          icon={<SlidersHorizontal className="h-4 w-4 text-cisco-blue" />}
          onDismiss={({ dontShowAgain }) => {
            if (dontShowAgain) window.localStorage.setItem(ALARM_RULES_INTRO_STORAGE_KEY, 'true');
            setShowIntro(false);
          }}
        >
          <p className="mb-3 text-gray-600 dark:text-gray-300">{ALARM_RULES_HELP.overview}</p>
          <AlarmRulesDiagram />
        </PageIntroFloat>
      )}

      {!embedded && (
        <PageHeader
          title="Alarm Rules"
          subtitle="Customize severities and auto-clear behavior for traps, syslogs, and events"
        />
      )}

      <Card className="p-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Alarm rule flow</h2>
          <InfoFloat title="Alarm rule flow" description={ALARM_RULES_HELP.overview} />
        </div>
        <div className="mt-3">
          <AlarmRulesDiagram />
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
                {editing ? `Edit ${editing.name}` : 'New customization rule'}
              </h2>
              <InfoFloat title="New customization rule" description={ALARM_RULES_HELP.form} />
            </div>
            <p className="text-xs text-gray-500">
              First matching enabled rule wins. Lower priority numbers run first.
            </p>
          </div>
          {editing && <Button variant="ghost" onClick={() => setEditing(null)}>Cancel edit</Button>}
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
          <Input label="Name" value={form.name} onChange={(e) => set('name', e.target.value)} required />
          <Input
            label="Priority"
            type="number"
            value={form.priority}
            onChange={(e) => set('priority', Number(e.target.value))}
            required
          />
          <Select
            label="Source"
            value={form.source_type}
            onChange={(e) => set('source_type', e.target.value as SourceType)}
            options={sourceOptions}
          />
          <Select
            label="Severity override"
            value={form.severity}
            onChange={(e) => set('severity', e.target.value as RuleSeverity)}
            options={severityOptions}
          />
          <Select
            label="Match field"
            value={form.match_field}
            onChange={(e) => set('match_field', e.target.value as MatchField)}
            options={matchFieldOptions}
          />
          <Select
            label="Operator"
            value={form.match_operator}
            onChange={(e) => set('match_operator', e.target.value as MatchOperator)}
            options={operatorOptions}
          />
          <Input
            label="Match pattern"
            value={form.match_pattern}
            onChange={(e) => set('match_pattern', e.target.value)}
            placeholder="1.3.6.1.4.1... or regex"
            required
          />
          <Input label="Category" value={form.category ?? ''} onChange={(e) => set('category', e.target.value)} />
          <Input label="Event type override" value={form.event_type ?? ''} onChange={(e) => set('event_type', e.target.value)} />
          <Input
            label="Correlation key template"
            value={form.correlation_key_template ?? ''}
            onChange={(e) => set('correlation_key_template', e.target.value)}
            placeholder="custom:{source_host}:{trap_oid}"
          />
          <label className="flex items-center gap-2 pt-6 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => set('enabled', e.target.checked)}
            />
            Enabled
          </label>
          <label className="flex items-center gap-2 pt-6 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={form.auto_clear}
              onChange={(e) => set('auto_clear', e.target.checked)}
            />
            Auto-clear matching alarm
          </label>
        </div>

        <div className="mt-3">
          <label className="mb-1 block text-xs font-medium text-gray-700 dark:text-gray-300">Message template</label>
          <textarea
            value={form.message_template ?? ''}
            onChange={(e) => set('message_template', e.target.value)}
            placeholder="Interface event from {source_host}. OID: {trap_oid}"
            className="min-h-20 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
          />
          <p className="mt-1 text-xs text-gray-500">
            Template variables: {'{source_host}'}, {'{trap_oid}'}, {'{event_type}'}, {'{message}'}, {'{correlation_key}'}, plus varbind_&lt;OID&gt; keys.
          </p>
        </div>

        {saveMutation.isError && <p className="mt-3 text-sm text-red-500">Failed to save alarm rule.</p>}

        <div className="mt-4 flex justify-end gap-2">
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={!form.name.trim() || !form.match_pattern.trim() || saveMutation.isPending}
          >
            {saveMutation.isPending ? 'Saving…' : editing ? 'Save changes' : 'Create rule'}
          </Button>
        </div>
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Configured rules</h2>
          <InfoFloat title="Configured rules" description={ALARM_RULES_HELP.list} />
        </div>
        {rulesQuery.isLoading && <p className="py-6 text-center text-sm text-gray-400">Loading rules…</p>}
        {!rulesQuery.isLoading && rules.length === 0 && (
          <EmptyState title="No alarm rules" description="Create a rule to customize trap, syslog, or event severity." />
        )}
        {rules.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {['Priority', 'Name', 'Source', 'Match', 'Severity', 'Auto-clear', 'Status', 'Actions'].map((h) => (
                    <th key={h} className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {rules.map((rule) => (
                  <tr key={rule.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                    <td className="px-4 py-2">{rule.priority}</td>
                    <td className="px-4 py-2 font-medium">{rule.name}</td>
                    <td className="px-4 py-2">{rule.source_type}</td>
                    <td className="px-4 py-2 font-mono text-xs">{rule.match_field} {rule.match_operator} {rule.match_pattern}</td>
                    <td className="px-4 py-2 capitalize">{rule.severity}</td>
                    <td className="px-4 py-2">{rule.auto_clear ? 'Yes' : 'No'}</td>
                    <td className="px-4 py-2">{rule.enabled ? 'Enabled' : 'Disabled'}</td>
                    <td className="px-4 py-2">
                      <div className="flex gap-3">
                        <button className="text-xs text-blue-600 hover:underline" onClick={() => setEditing(rule)}>Edit</button>
                        <button
                          className="text-xs text-red-500 hover:underline"
                          onClick={() => deleteMutation.mutate(rule.id)}
                          disabled={deleteMutation.isPending}
                        >
                          Delete
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
