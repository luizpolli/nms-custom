import { useState, type FormEvent, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, Database, FileText, Lightbulb, ListChecks, ShieldAlert } from 'lucide-react';
import { Badge, Button, Card, EmptyState, InfoFloat, Input, PageHeader, PageIntroFloat, Spinner } from '../../components/ui';
import { api } from '../../lib/api';

type Citation = {
  source_type: string;
  object_id: string;
  label: string;
  timestamp?: string | null;
  detail?: string | null;
};

type Advisory = {
  advisory_type: string;
  title: string;
  summary: string;
  recommendations: string[];
  citations: Citation[];
  advisory_only: boolean;
  generated_at: string;
};

const FALLBACK_GROUP_KEY = 'latest';
const INTRO_STORAGE_KEY = 'nms-aiops-intro-dismissed-v2';

const AI_OPS_HELP = {
  overview: 'AI Ops converts alarms and KPI evidence into advisory summaries. It does not execute changes; it cites the objects it used so operators can validate the recommendation before acting.',
  assistant: 'Ask evidence-grounded operational questions. The assistant retrieves recent alarms and KPI anomalies, redacts sensitive text, and requires citations in the answer.',
  alarmSummary: 'Summarizes one alarm group or the latest deduplicated group. Use it to understand severity, affected hosts, and first-pass actions.',
  kpiExplanation: 'Explains non-good KPI samples from the selected time window and shows the cited KPI rows behind the advisory.',
  reportNarrative: 'Builds a short operational narrative from recent alarms and KPI anomalies. Treat it as a draft, not a customer-ready RCA.',
  runbooks: 'Suggests runbook actions from active alarm categories. The output is advisory and should be validated against topology, timeline, and raw device data.',
};

function normalizeAiOpsText(value: string) {
  return value
    .replace(/^Sin datos para el grupo$/i, 'No data for this group')
    .replace(/^No encontré alarmas activas\/ack\/suprimidas con esa llave\.$/i, 'No active, acknowledged, or suppressed alarms were found for this key.')
    .replace(/^Grupo (.*):/i, 'Group $1:')
    .replace(/^Hay (\d+) alarma\(s\) relacionadas; peor severidad ([^.]+)\. Impacto observado en: (.*)\.$/i, 'Found $1 related alarm(s); worst severity is $2. Observed impact on: $3.')
    .replace(/sin host identificado/gi, 'no identified host')
    .replace(/^Sin anomalías KPI recientes$/i, 'No recent KPI anomalies')
    .replace(/^No hay muestras KPI non-good en la ventana solicitada\.$/i, 'No non-good KPI samples were found in the requested window.')
    .replace(/^(\d+) anomalía\(s\) KPI recientes$/i, '$1 recent KPI anomalies')
    .replace(/^Las métricas afectadas incluyen: (.*)\. Esto sugiere degradación observable, no causa raíz confirmada\.$/i, 'Affected metrics include: $1. This suggests observable degradation, not a confirmed root cause.')
    .replace(/^Correlaciona estas muestras con alarmas activas y cambios recientes\.$/i, 'Correlate these samples with active alarms and recent changes.')
    .replace(/^Valida si la anomalía aparece en SNMP y telemetry antes de escalar\.$/i, 'Validate whether the anomaly appears in both SNMP and telemetry before escalation.')
    .replace(/^Sugerencias de runbook$/i, 'Runbook suggestions')
    .replace(/^Sugerencias basadas en (\d+) alarma\(s\) activa\(s\) y categoría\(s\): (.*)\.$/i, 'Suggestions based on $1 active alarm(s) and category set: $2.')
    .replace(/^No hay runbook específico; usa timeline, topología, KPIs y auditoría para acotar causa antes de tocar producción\.$/i, 'No specific runbook is available; use the timeline, topology, KPIs, and audit data to narrow cause before touching production.')
    .replace(/^Narrativa operacional$/i, 'Operational narrative')
    .replace(/^En las últimas (\d+)h: (\d+) alarma\(s\) y (\d+) KPI\(s\) non-good\./i, 'In the last $1h: $2 alarm(s) and $3 non-good KPI(s).')
    .replace(/ Peor alarma: ([^ ]+) en ([^:]+):/i, ' Worst alarm: $1 on $2:')
    .replace(/^Usa esta narrativa como borrador; confirma con datos crudos antes de enviarla a clientes\.$/i, 'Use this narrative as a draft; confirm against raw data before sending it to customers.')
    .replace(/^No tengo evidencia suficiente para responder con citas\.$/i, 'I do not have enough evidence to answer with citations.')
    .replace(/^Resumen determinístico para:/i, 'Deterministic summary for:')
    .replace(/^Hallazgos:$/i, 'Findings:')
    .replace(/^Recomendación: revisa los elementos citados antes de actuar; este resumen es advisory y no confirma causa raíz\.$/i, 'Recommendation: review the cited items before acting; this summary is advisory and does not confirm root cause.')
    .replace(/^Revisa la alarma citada /i, 'Review the cited alarm ')
    .replace(/evidencia/gi, 'evidence')
    .replace(/citas/gi, 'citations');
}

function normalizeCitation(citation: Citation): Citation {
  return {
    ...citation,
    label: normalizeAiOpsText(citation.label),
    detail: citation.detail ? normalizeAiOpsText(citation.detail) : citation.detail,
  };
}

function normalizeAdvisory(advisory: Advisory): Advisory {
  return {
    ...advisory,
    title: normalizeAiOpsText(advisory.title),
    summary: normalizeAiOpsText(advisory.summary),
    recommendations: advisory.recommendations.map(normalizeAiOpsText),
    citations: advisory.citations.map(normalizeCitation),
  };
}

function normalizeAssistantAnswer(answer: AssistantAnswer): AssistantAnswer {
  return {
    ...answer,
    answer: normalizeAiOpsText(answer.answer),
    citations: answer.citations.map(normalizeCitation),
    rejected_reason: answer.rejected_reason ? normalizeAiOpsText(answer.rejected_reason) : answer.rejected_reason,
  };
}

function useAdvisory(key: string, url: string, params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['ai-ops', key, params],
    queryFn: () => api.get<Advisory>(url, { params }).then((r) => normalizeAdvisory(r.data)),
    staleTime: 30_000,
    retry: 1,
  });
}

function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations.length) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">No citations available yet.</p>;
  }
  return (
    <ul className="space-y-2">
      {citations.map((citation) => (
        <li key={`${citation.source_type}-${citation.object_id}`} className="rounded-md border border-gray-200 p-2 text-xs dark:border-gray-700">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="neutral">{citation.source_type}</Badge>
            <span className="font-medium text-gray-900 dark:text-gray-100">{citation.label}</span>
            {citation.timestamp && <span className="text-gray-500">{new Date(citation.timestamp).toLocaleString()}</span>}
          </div>
          <div className="mt-1 break-all text-gray-500">ID: {citation.object_id}</div>
          {citation.detail && <div className="mt-1 text-gray-600 dark:text-gray-300">{citation.detail}</div>}
        </li>
      ))}
    </ul>
  );
}

function AdvisoryCard({ title, description, icon, advisory, isLoading, isError }: { title: string; description: string; icon: ReactNode; advisory?: Advisory; isLoading: boolean; isError: boolean }) {
  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
          <InfoFloat title={title} description={description} />
        </div>
        <Badge variant="minor">Advisory only</Badge>
      </div>
      {isLoading && <Spinner />}
      {isError && <EmptyState title="No data" description="This advisory could not be generated from the current evidence." />}
      {!isLoading && !isError && advisory && (
        <>
          <div>
            <h3 className="font-medium text-gray-900 dark:text-gray-100">{advisory.title}</h3>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{advisory.summary}</p>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">Recommendations</h4>
            {advisory.recommendations.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-200">
                {advisory.recommendations.map((rec) => <li key={rec}>{rec}</li>)}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">No recommendations generated.</p>
            )}
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">Citations / evidence</h4>
            <CitationList citations={advisory.citations} />
          </div>
        </>
      )}
    </Card>
  );
}

type AssistantAnswer = {
  question: string;
  answer: string;
  citations: Citation[];
  provider: string;
  advisory_only: boolean;
  rejected_reason?: string | null;
  generated_at: string;
};

function AssistantPanel() {
  const [question, setQuestion] = useState('');
  const [hours, setHours] = useState(24);
  const mutation = useMutation({
    mutationFn: (payload: { question: string; kpi_hours: number }) =>
      api.post<AssistantAnswer>('/ai-ops/assistant/ask', payload).then((r) => r.data),
  });

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    mutation.mutate({ question: q, kpi_hours: hours });
  };

  const answer = mutation.data ? normalizeAssistantAnswer(mutation.data) : undefined;
  const disabled = mutation.isPending;
  const isUnavailable =
    mutation.isError && (mutation.error as { response?: { status?: number } })?.response?.status === 503;

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            AI Ops assistant with guardrails
          </h2>
          <InfoFloat title="AI Ops assistant" description={AI_OPS_HELP.assistant} />
        </div>
        <Badge variant="minor">Advisory only</Badge>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Every answer must cite evidence from alarms and KPIs. If the assistant is disabled, the backend
        returns 503. Enable it with <code>AI_OPS_LLM_ENABLED=true</code>.
      </p>
      <form onSubmit={onSubmit} className="space-y-3">
        <Input
          placeholder="Example: what is happening with critical links in the last few hours?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          disabled={disabled}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-300">
            KPI window (hours):
            <input
              type="number"
              min={1}
              max={168}
              value={hours}
              onChange={(e) => setHours(Math.max(1, Math.min(168, Number(e.target.value) || 1)))}
              className="ml-2 w-20 rounded-md border border-gray-300 px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-800"
              disabled={disabled}
            />
          </label>
          <Button type="submit" disabled={disabled || !question.trim()}>
            {disabled ? 'Processing...' : 'Ask'}
          </Button>
        </div>
      </form>
      {mutation.isPending && <Spinner />}
      {isUnavailable && (
        <EmptyState
          title="Assistant disabled"
          description="The backend returned 503. Enable AI_OPS_LLM_ENABLED in the configuration to use this endpoint."
        />
      )}
      {mutation.isError && !isUnavailable && (
        <EmptyState title="Error" description="The question could not be processed." />
      )}
      {answer && (
        <div className="space-y-3">
          {answer.rejected_reason && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100">
              Answer rejected by guardrails: {answer.rejected_reason}
            </div>
          )}
          <div>
            <div className="mb-1 text-xs uppercase tracking-wide text-gray-500">
              Provider: {answer.provider}
            </div>
            <pre className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-sm text-gray-800 dark:bg-gray-900 dark:text-gray-100">
              {answer.answer}
            </pre>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
              Citations / evidence
            </h4>
            <CitationList citations={answer.citations} />
          </div>
        </div>
      )}
    </Card>
  );
}

function FlowNode({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
        {icon}
        <span>{title}</span>
      </div>
      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{text}</p>
    </div>
  );
}

function AIOpsFlowDiagram({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? 'space-y-2' : 'rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-950'}>
      {!compact && (
        <div className="mb-3 flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">AI Ops evidence flow</h2>
          <InfoFloat title="AI Ops evidence flow" description={AI_OPS_HELP.overview} />
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] md:items-center">
        <FlowNode icon={<Database className="h-4 w-4 text-cisco-blue" />} title="Evidence" text="Alarms, KPI anomalies, topology context, and report data." />
        <div className="hidden text-center text-xl text-gray-400 md:block">-&gt;</div>
        <FlowNode icon={<ShieldAlert className="h-4 w-4 text-amber-500" />} title="Guardrails" text="Redaction, limits, advisory-only behavior, and citation requirements." />
        <div className="hidden text-center text-xl text-gray-400 md:block">-&gt;</div>
        <FlowNode icon={<Bot className="h-4 w-4 text-indigo-500" />} title="Advisory" text="Summaries, anomaly explanations, runbooks, and assistant answers." />
        <div className="hidden text-center text-xl text-gray-400 md:block">-&gt;</div>
        <FlowNode icon={<ListChecks className="h-4 w-4 text-emerald-500" />} title="Operator" text="Validate citations, confirm root cause, then decide the next action." />
      </div>
    </div>
  );
}

function AIOpsIntro({ onDismiss }: { onDismiss: (options: { dontShowAgain: boolean }) => void }) {
  return (
    <PageIntroFloat title="AI Ops quick guide" icon={<Bot className="h-4 w-4 text-cisco-blue" />} onDismiss={onDismiss}>
      <p className="mb-3 text-gray-600 dark:text-gray-300">{AI_OPS_HELP.overview}</p>
      <AIOpsFlowDiagram compact />
    </PageIntroFloat>
  );
}

export function AIOpsPage() {
  const [showIntro, setShowIntro] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(INTRO_STORAGE_KEY) !== 'true';
  });
  const alarmSummary = useAdvisory('alarm-group-summary', `/ai-ops/alarm-groups/${encodeURIComponent(FALLBACK_GROUP_KEY)}/summary`);
  const kpiExplanation = useAdvisory('kpi-anomalies', '/ai-ops/kpis/anomalies/explain', { hours: 24, limit: 20 });
  const reportNarrative = useAdvisory('report-narrative', '/ai-ops/reports/narrative', { hours: 24 });
  const runbooks = useAdvisory('runbooks', '/ai-ops/runbooks/suggest', { limit: 10 });

  const dismissIntro = ({ dontShowAgain }: { dontShowAgain: boolean }) => {
    if (dontShowAgain) window.localStorage.setItem(INTRO_STORAGE_KEY, 'true');
    setShowIntro(false);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Ops"
        description="Evidence-grounded operational advisories. They cite data, avoid automated changes, and still require human validation."
      />
      {showIntro && <AIOpsIntro onDismiss={dismissIntro} />}
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
        All cards are <strong>advisory-only</strong>: they summarize existing data and show cited evidence when available.
      </div>
      <AIOpsFlowDiagram />
      <AssistantPanel />
      <div className="grid gap-5 xl:grid-cols-2">
        <AdvisoryCard title="Alarm group summary" description={AI_OPS_HELP.alarmSummary} icon={<ShieldAlert className="h-5 w-5 text-red-500" />} advisory={alarmSummary.data} isLoading={alarmSummary.isLoading} isError={alarmSummary.isError} />
        <AdvisoryCard title="KPI anomaly explanation" description={AI_OPS_HELP.kpiExplanation} icon={<Lightbulb className="h-5 w-5 text-amber-500" />} advisory={kpiExplanation.data} isLoading={kpiExplanation.isLoading} isError={kpiExplanation.isError} />
        <AdvisoryCard title="Report narrative" description={AI_OPS_HELP.reportNarrative} icon={<FileText className="h-5 w-5 text-blue-500" />} advisory={reportNarrative.data} isLoading={reportNarrative.isLoading} isError={reportNarrative.isError} />
        <AdvisoryCard title="Runbook suggestions" description={AI_OPS_HELP.runbooks} icon={<ListChecks className="h-5 w-5 text-emerald-500" />} advisory={runbooks.data} isLoading={runbooks.isLoading} isError={runbooks.isError} />
      </div>
    </div>
  );
}

export default AIOpsPage;
