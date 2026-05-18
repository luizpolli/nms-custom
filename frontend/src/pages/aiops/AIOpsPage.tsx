import { useState, type FormEvent, type ReactNode } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Bot, FileText, Lightbulb, ListChecks, ShieldAlert } from 'lucide-react';
import { Badge, Button, Card, EmptyState, Input, PageHeader, Spinner } from '../../components/ui';
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

function useAdvisory(key: string, url: string, params?: Record<string, unknown>) {
  return useQuery({
    queryKey: ['ai-ops', key, params],
    queryFn: () => api.get<Advisory>(url, { params }).then((r) => r.data),
    staleTime: 30_000,
    retry: 1,
  });
}

function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations.length) {
    return <p className="text-sm text-gray-500 dark:text-gray-400">Sin citas disponibles todavía.</p>;
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

function AdvisoryCard({ title, icon, advisory, isLoading, isError }: { title: string; icon: ReactNode; advisory?: Advisory; isLoading: boolean; isError: boolean }) {
  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">{title}</h2>
        </div>
        <Badge variant="minor">Advisory only</Badge>
      </div>
      {isLoading && <Spinner />}
      {isError && <EmptyState title="Sin datos" description="No se pudo generar esta recomendación con la información actual." />}
      {!isLoading && !isError && advisory && (
        <>
          <div>
            <h3 className="font-medium text-gray-900 dark:text-gray-100">{advisory.title}</h3>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{advisory.summary}</p>
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">Recomendaciones</h4>
            {advisory.recommendations.length ? (
              <ul className="list-disc space-y-1 pl-5 text-sm text-gray-700 dark:text-gray-200">
                {advisory.recommendations.map((rec) => <li key={rec}>{rec}</li>)}
              </ul>
            ) : (
              <p className="text-sm text-gray-500">Sin recomendaciones generadas.</p>
            )}
          </div>
          <div>
            <h4 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">Citas / evidencia</h4>
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

  const answer = mutation.data;
  const disabled = mutation.isPending;
  const isUnavailable =
    mutation.isError && (mutation.error as { response?: { status?: number } })?.response?.status === 503;

  return (
    <Card className="space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Asistente AI Ops (con guardrails)
          </h2>
        </div>
        <Badge variant="minor">Advisory only</Badge>
      </div>
      <p className="text-sm text-gray-600 dark:text-gray-300">
        Toda respuesta cita evidencia (alarmas/KPIs). Si el assistant está deshabilitado, el backend
        responde 503 — actívalo con <code>AI_OPS_LLM_ENABLED=true</code>.
      </p>
      <form onSubmit={onSubmit} className="space-y-3">
        <Input
          placeholder="Ej. ¿qué pasa con los enlaces críticos en las últimas horas?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          disabled={disabled}
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-gray-600 dark:text-gray-300">
            Ventana KPI (horas):
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
            {disabled ? 'Procesando…' : 'Preguntar'}
          </Button>
        </div>
      </form>
      {mutation.isPending && <Spinner />}
      {isUnavailable && (
        <EmptyState
          title="Assistant deshabilitado"
          description="El backend respondió 503. Habilita AI_OPS_LLM_ENABLED en la configuración para usar este endpoint."
        />
      )}
      {mutation.isError && !isUnavailable && (
        <EmptyState title="Error" description="No se pudo procesar la pregunta." />
      )}
      {answer && (
        <div className="space-y-3">
          {answer.rejected_reason && (
            <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100">
              Respuesta rechazada por guardrails: {answer.rejected_reason}
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
              Citas / evidencia
            </h4>
            <CitationList citations={answer.citations} />
          </div>
        </div>
      )}
    </Card>
  );
}

export function AIOpsPage() {
  const alarmSummary = useAdvisory('alarm-group-summary', `/ai-ops/alarm-groups/${encodeURIComponent(FALLBACK_GROUP_KEY)}/summary`);
  const kpiExplanation = useAdvisory('kpi-anomalies', '/ai-ops/kpis/anomalies/explain', { hours: 24, limit: 20 });
  const reportNarrative = useAdvisory('report-narrative', '/ai-ops/reports/narrative', { hours: 24 });
  const runbooks = useAdvisory('runbooks', '/ai-ops/runbooks/suggest', { limit: 10 });

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI Ops"
        description="Asistencias determinísticas con citas. No ejecutan cambios ni sustituyen validación humana. Sí, tristemente todavía hay que pensar."
      />
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100">
        Todas las tarjetas son <strong>advisory-only</strong>: resumen datos existentes y muestran evidencia citada cuando existe.
      </div>
      <AssistantPanel />
      <div className="grid gap-5 xl:grid-cols-2">
        <AdvisoryCard title="Resumen de grupo de alarmas" icon={<ShieldAlert className="h-5 w-5 text-red-500" />} advisory={alarmSummary.data} isLoading={alarmSummary.isLoading} isError={alarmSummary.isError} />
        <AdvisoryCard title="Explicación de anomalías KPI" icon={<Lightbulb className="h-5 w-5 text-amber-500" />} advisory={kpiExplanation.data} isLoading={kpiExplanation.isLoading} isError={kpiExplanation.isError} />
        <AdvisoryCard title="Narrativa de reporte" icon={<FileText className="h-5 w-5 text-blue-500" />} advisory={reportNarrative.data} isLoading={reportNarrative.isLoading} isError={reportNarrative.isError} />
        <AdvisoryCard title="Sugerencias de runbook" icon={<ListChecks className="h-5 w-5 text-emerald-500" />} advisory={runbooks.data} isLoading={runbooks.isLoading} isError={runbooks.isError} />
      </div>
    </div>
  );
}

export default AIOpsPage;
