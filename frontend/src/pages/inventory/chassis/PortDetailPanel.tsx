import { type ReactNode, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Info, Power, PowerOff, X, XCircle, Zap } from 'lucide-react';
import { api } from '../../../lib/api';
import { Badge, Spinner } from '../../../components/ui';

// ── Types ────────────────────────────────────────────────────────────────────

export type PortDetailData = {
  deviceId: string;
  physicalIndex: number;
  component: {
    physicalIndex: number;
    name?: string | null;
    description?: string | null;
    modelName?: string | null;
    serialNumber?: string | null;
    hardwareVersion?: string | null;
    firmwareVersion?: string | null;
    softwareVersion?: string | null;
    manufacturer?: string | null;
    alias?: string | null;
    isFru?: boolean | null;
    physicalClass?: number | null;
  };
  interface?: {
    id: string;
    name: string;
    alias?: string | null;
    adminStatus?: string | null;
    operStatus?: string | null;
    speedBps?: number | null;
    description?: string | null;
    macAddress?: string | null;
    role?: string | null;
    inOctets?: number | null;
    outOctets?: number | null;
    inErrors?: number | null;
    outErrors?: number | null;
  } | null;
  alarms: {
    id: string;
    severity: string;
    category: string;
    eventType: string;
    message: string;
    state: string;
    lastSeen?: string | null;
    firstSeen?: string | null;
    occurrenceCount: number;
    ackBy?: string | null;
  }[];
};

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatSpeedBps(speed?: number | null) {
  if (!speed) return '-';
  if (speed >= 1_000_000_000) return `${(speed / 1_000_000_000).toFixed(1)} Gbps`;
  if (speed >= 1_000_000) return `${(speed / 1_000_000).toFixed(1)} Mbps`;
  if (speed >= 1_000) return `${(speed / 1_000).toFixed(1)} Kbps`;
  return `${speed} bps`;
}

function formatDateTime(iso?: string | null) {
  if (!iso) return '-';
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const SEVERITY_CONFIG: Record<string, { label: string; colorClass: string; icon: React.ReactNode }> = {
  critical: { label: 'Critical', colorClass: 'bg-red-600 text-white', icon: <XCircle className="h-3.5 w-3.5" /> },
  major: { label: 'Major', colorClass: 'bg-orange-500 text-white', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  minor: { label: 'Minor', colorClass: 'bg-yellow-400 text-gray-900', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
  warning: { label: 'Warning', colorClass: 'bg-yellow-200 text-yellow-800', icon: <Info className="h-3.5 w-3.5" /> },
  info: { label: 'Info', colorClass: 'bg-blue-100 text-blue-800', icon: <Info className="h-3.5 w-3.5" /> },
};

function SeverityBadge({ severity }: { severity: string }) {
  const config = SEVERITY_CONFIG[severity.toLowerCase()] ?? {
    label: severity,
    colorClass: 'bg-gray-200 text-gray-700',
    icon: <Info className="h-3.5 w-3.5" />,
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${config.colorClass}`}>
      {config.icon}
      {config.label}
    </span>
  );
}

function StatusDot({ status }: { status?: string | null }) {
  const up = status === 'up' || status === 'on';
  const down = status === 'down' || status === 'off';
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${
        up ? 'bg-green-500' : down ? 'bg-red-500' : 'bg-gray-400'
      }`}
    />
  );
}

function MetricRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-gray-100 pb-2 last:border-0 dark:border-gray-800">
      <span className="shrink-0 text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right font-medium text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}

// ── Port control ─────────────────────────────────────────────────────────────

type AdminStatusAction = 'enable' | 'disable';

export type AdminStatusResult = {
  interfaceName: string;
  action: AdminStatusAction;
  success: boolean;
  adminStatus?: string | null;
  output?: string | null;
  error?: string | null;
};

export function extractAdminStatusError(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const response = (error as { response?: { status?: number; data?: { detail?: unknown } } })
      .response;
    if (response?.status === 403) return 'Not permitted — admin role required.';
    if (typeof response?.data?.detail === 'string') return response.data.detail;
  }
  return 'Request failed.';
}

function PortControlSection({
  deviceId,
  physicalIndex,
  interfaceId,
  interfaceName,
}: {
  deviceId: string;
  physicalIndex: number;
  interfaceId: string;
  interfaceName: string;
}) {
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<AdminStatusAction | null>(null);

  const mutation = useMutation<AdminStatusResult, unknown, AdminStatusAction>({
    mutationFn: (action) =>
      api
        .post<AdminStatusResult>(
          `/devices/${deviceId}/interfaces/${interfaceId}/admin-status`,
          { action },
        )
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['port-detail', deviceId, physicalIndex] });
      queryClient.invalidateQueries({ queryKey: ['chassis-managed-interfaces', deviceId] });
    },
  });

  const confirmLabel = pendingAction === 'disable' ? 'shutdown' : 'no shutdown';

  return (
    <section>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
        Port control
      </p>
      <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3 text-sm space-y-2 dark:border-gray-700 dark:bg-gray-800">
        {pendingAction === null ? (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => setPendingAction('enable')}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              <Power className="h-4 w-4" />
              Enable
            </button>
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => setPendingAction('disable')}
              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              <PowerOff className="h-4 w-4" />
              Disable
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-gray-800 dark:text-gray-200">
              Send <span className="font-mono font-semibold">{confirmLabel}</span> to{' '}
              <span className="font-semibold">{interfaceName}</span>?
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={mutation.isPending}
                onClick={() => {
                  mutation.mutate(pendingAction);
                  setPendingAction(null);
                }}
                className="flex-1 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Confirm
              </button>
              <button
                type="button"
                onClick={() => setPendingAction(null)}
                className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {mutation.isPending && (
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
            <Spinner />
            <span>Applying configuration…</span>
          </div>
        )}

        {mutation.isSuccess &&
          (mutation.data.success ? (
            <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4 shrink-0" />
              {mutation.data.interfaceName} {mutation.data.action}d.
            </div>
          ) : (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
              <p className="font-medium">Device rejected the change.</p>
              {(mutation.data.error || mutation.data.output) && (
                <pre className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
                  {mutation.data.error ?? mutation.data.output}
                </pre>
              )}
            </div>
          ))}

        {mutation.isError && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
            {extractAdminStatusError(mutation.error)}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Main Panel ────────────────────────────────────────────────────────────────

interface PortDetailPanelProps {
  deviceId: string;
  physicalIndex: number;
  onClose: () => void;
}

export function PortDetailPanel({ deviceId, physicalIndex, onClose }: PortDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null);

  const query = useQuery<PortDetailData>({
    queryKey: ['port-detail', deviceId, physicalIndex],
    queryFn: () =>
      api
        .get<PortDetailData>(`/devices/${deviceId}/chassis/ports/${physicalIndex}`)
        .then((r) => r.data),
    enabled: Boolean(deviceId) && physicalIndex != null,
    staleTime: 30_000,
  });

  // Close on outside click
  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        onClose();
      }
    }
    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    // Backdrop overlay — covers the page; clicks outside the panel trigger close via handlePointerDown
    <div className="fixed inset-0 z-40 overflow-hidden">
      {/* Dim overlay */}
      <div className="absolute inset-0 bg-black/20 dark:bg-black/40" />

      {/* Slide-out panel from the right */}
      <div
        ref={panelRef}
        className="absolute right-0 top-0 flex h-full w-full max-w-sm flex-col overflow-hidden bg-white shadow-2xl ring-1 ring-gray-200 dark:bg-gray-900 dark:ring-gray-700"
        style={{ animation: 'slideInRight 180ms ease-out' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Port Detail
            </p>
            <h3 className="truncate text-base font-semibold text-gray-900 dark:text-gray-100">
              {query.data?.component.name ?? `Physical index ${physicalIndex}`}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close port detail panel"
            className="ml-3 shrink-0 rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
          {query.isLoading && (
            <div className="flex items-center justify-center py-12">
              <Spinner />
            </div>
          )}

          {query.isError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
              Failed to load port details.
            </div>
          )}

          {query.data && (
            <>
              {/* Component Info */}
              <section>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  Component
                </p>
                <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3 text-sm space-y-2 dark:border-gray-700 dark:bg-gray-800">
                  <MetricRow label="Name" value={query.data.component.name ?? '-'} />
                  <MetricRow label="Model" value={query.data.component.modelName ?? '-'} />
                  <MetricRow label="Serial" value={query.data.component.serialNumber ?? '-'} />
                  <MetricRow label="HW version" value={query.data.component.hardwareVersion ?? '-'} />
                  {query.data.component.firmwareVersion && (
                    <MetricRow label="FW version" value={query.data.component.firmwareVersion} />
                  )}
                  <MetricRow label="Manufacturer" value={query.data.component.manufacturer ?? '-'} />
                  <MetricRow label="FRU" value={query.data.component.isFru ? 'Yes' : 'No'} />
                  <MetricRow label="Physical index" value={String(query.data.component.physicalIndex)} />
                </div>
              </section>

              {/* Interface Status */}
              <section>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                    Interface
                  </p>
                  {query.data.interface ? (
                    <Badge variant="success">Bound</Badge>
                  ) : (
                    <Badge variant="default">Unbound</Badge>
                  )}
                </div>
                {query.data.interface ? (
                  <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3 text-sm space-y-2 dark:border-gray-700 dark:bg-gray-800">
                    <MetricRow
                      label="Oper status"
                      value={
                        <span className="inline-flex items-center gap-1.5">
                          <StatusDot status={query.data.interface.operStatus} />
                          <span>{query.data.interface.operStatus ?? '-'}</span>
                        </span>
                      }
                    />
                    <MetricRow
                      label="Admin status"
                      value={
                        <span className="inline-flex items-center gap-1.5">
                          <StatusDot status={query.data.interface.adminStatus} />
                          <span>{query.data.interface.adminStatus ?? '-'}</span>
                        </span>
                      }
                    />
                    <MetricRow label="Speed" value={formatSpeedBps(query.data.interface.speedBps)} />
                    {query.data.interface.alias && (
                      <MetricRow label="Alias" value={query.data.interface.alias} />
                    )}
                    {query.data.interface.description && (
                      <MetricRow label="Description" value={query.data.interface.description} />
                    )}
                    {query.data.interface.macAddress && (
                      <MetricRow label="MAC" value={query.data.interface.macAddress} />
                    )}
                    {query.data.interface.role && (
                      <MetricRow label="Role" value={query.data.interface.role} />
                    )}
                    {(query.data.interface.inOctets != null || query.data.interface.outOctets != null) && (
                      <>
                        <MetricRow
                          label="In octets"
                          value={query.data.interface.inOctets != null ? String(query.data.interface.inOctets) : '-'}
                        />
                        <MetricRow
                          label="Out octets"
                          value={query.data.interface.outOctets != null ? String(query.data.interface.outOctets) : '-'}
                        />
                      </>
                    )}
                    {(query.data.interface.inErrors != null || query.data.interface.outErrors != null) && (
                      <>
                        <MetricRow
                          label="In errors"
                          value={query.data.interface.inErrors != null ? String(query.data.interface.inErrors) : '-'}
                        />
                        <MetricRow
                          label="Out errors"
                          value={query.data.interface.outErrors != null ? String(query.data.interface.outErrors) : '-'}
                        />
                      </>
                    )}
                  </div>
                ) : (
                  <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
                    No managed interface matched this component.
                  </p>
                )}
              </section>

              {/* Port Control */}
              {query.data.interface && (
                <PortControlSection
                  deviceId={deviceId}
                  physicalIndex={physicalIndex}
                  interfaceId={query.data.interface.id}
                  interfaceName={query.data.interface.name}
                />
              )}

              {/* Active Alarms */}
              <section>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                    Active alarms
                  </p>
                  {query.data.alarms.length > 0 && (
                    <Badge variant="danger">{query.data.alarms.length} active</Badge>
                  )}
                </div>
                {query.data.alarms.length === 0 ? (
                  <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-400">
                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                    No active alarms for this device.
                  </div>
                ) : (
                  <ul className="space-y-2">
                    {query.data.alarms.map((alarm) => (
                      <li
                        key={alarm.id}
                        className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800"
                      >
                        <div className="mb-1 flex items-start justify-between gap-2">
                          <SeverityBadge severity={alarm.severity} />
                          <span className="text-xs text-gray-400 dark:text-gray-500">
                            {formatDateTime(alarm.lastSeen)}
                          </span>
                        </div>
                        <p className="text-gray-800 dark:text-gray-200">{alarm.message}</p>
                        {alarm.occurrenceCount > 1 && (
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            <Zap className="mr-0.5 inline h-3 w-3" />
                            {alarm.occurrenceCount}× occurrences
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
