import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Download, ShieldCheck, TriangleAlert } from 'lucide-react';
import { api } from '../../../lib/api';
import { Badge, Button, Card, EmptyState, Spinner } from '../../../components/ui';

export type ConfigBackupMeta = {
  id: string;
  kind: 'backup' | 'golden';
  contentHash: string;
  sizeBytes: number;
  collectedBy: string;
  createdAt: string | null;
};

export type ConfigDrift = {
  status: 'in_sync' | 'drift' | 'no_golden' | 'no_backup';
  goldenId: string | null;
  backupId: string | null;
  diff: string;
  added: number;
  removed: number;
};

const DRIFT_BADGES: Record<ConfigDrift['status'], { label: string; variant: 'success' | 'danger' | 'default' }> = {
  in_sync: { label: 'In sync', variant: 'success' },
  drift: { label: 'Drift detected', variant: 'danger' },
  no_golden: { label: 'No golden config', variant: 'default' },
  no_backup: { label: 'No backup yet', variant: 'default' },
};

function diffLineClass(line: string): string {
  if (line.startsWith('+') && !line.startsWith('+++')) return 'text-green-700 dark:text-green-400';
  if (line.startsWith('-') && !line.startsWith('---')) return 'text-red-700 dark:text-red-400';
  if (line.startsWith('@@')) return 'text-blue-600 dark:text-blue-400';
  return 'text-gray-600 dark:text-gray-400';
}

function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-gray-200 bg-gray-50 p-3 font-mono text-xs leading-5 dark:border-gray-700 dark:bg-gray-900">
      {diff.split('\n').map((line, i) => (
        <div key={i} className={diffLineClass(line)}>
          {line || ' '}
        </div>
      ))}
    </pre>
  );
}

function formatBytes(bytes: number) {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function formatDate(iso: string | null) {
  return iso ? new Date(iso).toLocaleString() : '—';
}

export function ConfigComplianceTab({ deviceId }: { deviceId: string }) {
  const queryClient = useQueryClient();

  const driftQuery = useQuery<ConfigDrift>({
    queryKey: ['config-drift', deviceId],
    queryFn: () => api.get(`/devices/${deviceId}/config-drift`).then((r) => r.data),
  });

  const backupsQuery = useQuery<ConfigBackupMeta[]>({
    queryKey: ['config-backups', deviceId],
    queryFn: () => api.get(`/devices/${deviceId}/config-backups`).then((r) => r.data),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['config-drift', deviceId] });
    queryClient.invalidateQueries({ queryKey: ['config-backups', deviceId] });
  };

  const collectMutation = useMutation({
    mutationFn: () => api.post(`/devices/${deviceId}/config-backups`).then((r) => r.data),
    onSuccess: invalidate,
  });

  const promoteMutation = useMutation({
    mutationFn: (backupId: string) =>
      api.post(`/devices/${deviceId}/golden-config`, { backup_id: backupId }).then((r) => r.data),
    onSuccess: invalidate,
  });

  const drift = driftQuery.data;
  const backups = backupsQuery.data ?? [];
  const badge = drift ? DRIFT_BADGES[drift.status] : null;

  return (
    <div className="space-y-4">
      {/* Drift status */}
      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-gray-500" />
            <h3 className="font-semibold text-gray-700 dark:text-gray-100">Config compliance</h3>
            {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
            {drift?.status === 'drift' && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                +{drift.added} / -{drift.removed} lines vs golden
              </span>
            )}
          </div>
          <Button onClick={() => collectMutation.mutate()} disabled={collectMutation.isPending}>
            <Download className={`mr-1 h-4 w-4 ${collectMutation.isPending ? 'animate-pulse' : ''}`} />
            Collect backup now
          </Button>
        </div>

        {collectMutation.isError && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
            Backup failed — check the device SSH credential and reachability.
          </p>
        )}
        {collectMutation.isSuccess && (
          <p className="flex items-center gap-1.5 text-sm text-green-700 dark:text-green-400">
            <CheckCircle2 className="h-4 w-4" />
            {collectMutation.data?.deduplicated
              ? 'Config unchanged since last backup (deduplicated).'
              : 'Backup stored.'}
          </p>
        )}

        {driftQuery.isLoading && <Spinner />}
        {drift?.status === 'no_golden' && backups.length > 0 && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Promote a backup below to golden to start tracking drift.
          </p>
        )}
        {drift?.status === 'drift' && (
          <div className="space-y-2">
            <p className="flex items-center gap-1.5 text-sm text-red-700 dark:text-red-400">
              <TriangleAlert className="h-4 w-4" />
              Running config differs from the golden baseline:
            </p>
            <DiffView diff={drift.diff} />
          </div>
        )}
      </Card>

      {/* Backups list */}
      <Card className="p-4 space-y-3">
        <h3 className="font-semibold text-gray-700 dark:text-gray-100">Config backups</h3>
        {backupsQuery.isLoading && <Spinner />}
        {!backupsQuery.isLoading && backups.length === 0 && (
          <EmptyState
            title="No backups"
            description="Collect a backup to start the configuration history."
          />
        )}
        {backups.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
            <table className="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  {['Kind', 'Collected', 'Hash', 'Size', 'By', ''].map((h, i) => (
                    <th
                      key={i}
                      className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                {backups.map((backup) => (
                  <tr key={backup.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                    <td className="px-3 py-2">
                      <Badge variant={backup.kind === 'golden' ? 'success' : 'default'}>
                        {backup.kind}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-200">
                      {formatDate(backup.createdAt)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-500 dark:text-gray-400">
                      {backup.contentHash.slice(0, 12)}
                    </td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">
                      {formatBytes(backup.sizeBytes)}
                    </td>
                    <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{backup.collectedBy}</td>
                    <td className="px-3 py-2 text-right">
                      {backup.kind === 'backup' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => promoteMutation.mutate(backup.id)}
                          disabled={promoteMutation.isPending}
                        >
                          Set as golden
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {promoteMutation.isError && (
          <p className="text-sm text-red-700 dark:text-red-400">
            Failed to set golden config — admin role required.
          </p>
        )}
      </Card>
    </div>
  );
}
