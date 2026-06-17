import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Play, RefreshCw, Save, Trash2 } from 'lucide-react';
import { Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner } from '../../components/ui';
import { api } from '../../lib/api';

type BackupEntry = {
  name: string;
  size_bytes: number;
  files: string[];
  has_manifest: boolean;
};

type BackupConfig = {
  enabled: boolean;
  schedule: string;
  destination: string;
  dest_path: string;
  skip_redis: boolean;
  include_volumes: boolean;
  retain_days: number;
};

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function fmtTs(name: string): string {
  const m = name.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/);
  if (!m) return name;
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]}`;
}

export function BackupsPanel() {
  const qc = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [configDirty, setConfigDirty] = useState(false);
  const [localConfig, setLocalConfig] = useState<BackupConfig | null>(null);

  const { data: backups = [], isLoading: loadingBackups } = useQuery<BackupEntry[]>({
    queryKey: ['system', 'backups'],
    queryFn: () => api.get('/system/backups').then((r) => r.data as BackupEntry[]),
  });

  const { data: remoteConfig, isLoading: loadingConfig } = useQuery<BackupConfig>({
    queryKey: ['system', 'backup-config'],
    queryFn: () => api.get('/system/backup-config').then((r) => r.data as BackupConfig),
  });

  useEffect(() => {
    if (remoteConfig && !configDirty) setLocalConfig(remoteConfig);
  }, [remoteConfig, configDirty]);

  const config = localConfig ?? remoteConfig;

  const triggerBackup = useMutation({
    mutationFn: () => api.post('/system/backups', { skip_redis: false, include_volumes: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['system', 'backups'] }),
  });

  const deleteBackup = useMutation({
    mutationFn: (name: string) => api.delete(`/system/backups/${name}`),
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ['system', 'backups'] });
    },
  });

  const saveConfig = useMutation({
    mutationFn: (cfg: BackupConfig) => api.put('/system/backup-config', cfg),
    onSuccess: () => {
      setConfigDirty(false);
      qc.invalidateQueries({ queryKey: ['system', 'backup-config'] });
    },
  });

  function patchConfig(patch: Partial<BackupConfig>) {
    setLocalConfig((prev) => ({ ...(prev ?? remoteConfig)!, ...patch } as BackupConfig));
    setConfigDirty(true);
  }

  return (
    <div className="space-y-6">
      {/* Actions bar */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {backups.length} backup{backups.length !== 1 ? 's' : ''} stored
        </p>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => qc.invalidateQueries({ queryKey: ['system', 'backups'] })}
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => triggerBackup.mutate()}
            disabled={triggerBackup.isPending}
          >
            <Play className="h-4 w-4" />
            {triggerBackup.isPending ? 'Running…' : 'Run Backup Now'}
          </Button>
        </div>
      </div>

      {triggerBackup.isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-700 dark:bg-red-950 dark:text-red-300">
          Backup failed. Make sure the Docker socket is mounted and the stack is running.
        </div>
      )}

      {/* Backup history */}
      <Card>
        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Backup History</h3>
        </div>
        {loadingBackups ? (
          <div className="flex items-center justify-center py-12"><Spinner /></div>
        ) : backups.length === 0 ? (
          <EmptyState
            title="No backups yet"
            description="Click 'Run Backup Now' to create the first backup."
            icon={<Download className="h-8 w-8" />}
          />
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700">
            {backups.map((b) => (
              <div key={b.name} className="flex items-center justify-between px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100 font-mono">
                    {fmtTs(b.name)}
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                    {fmtBytes(b.size_bytes)} · {b.files.length} files
                    {b.files.some((f) => f.endsWith('.dump')) && ' · PostgreSQL'}
                    {b.files.some((f) => f.endsWith('.rdb')) && ' · Redis'}
                  </p>
                </div>
                <div className="ml-4 flex items-center gap-2 shrink-0">
                  {b.has_manifest && <Badge variant="default">manifest</Badge>}
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => setDeleteTarget(b.name)}
                    title="Delete backup"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Backup configuration */}
      <Card>
        <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Backup Configuration</h3>
        </div>
        {loadingConfig || !config ? (
          <div className="flex items-center justify-center py-12"><Spinner /></div>
        ) : (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-3">
              <input
                id="backup-enabled"
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => patchConfig({ enabled: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-cisco-blue"
              />
              <label htmlFor="backup-enabled" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Enable scheduled backups
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  Cron schedule
                </label>
                <Input
                  value={config.schedule}
                  onChange={(e) => patchConfig({ schedule: e.target.value })}
                  placeholder="0 2 * * *"
                  className="font-mono text-sm"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
                  Retain (days)
                </label>
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={String(config.retain_days)}
                  onChange={(e) => patchConfig({ retain_days: Number(e.target.value) })}
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
                Destination
              </label>
              <Select
                value={config.destination}
                onChange={(e) => patchConfig({ destination: e.target.value })}
              >
                <option value="local">Local path</option>
                <option value="sftp">SFTP / SCP</option>
                <option value="s3">S3 / MinIO</option>
              </Select>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-400">
                Backup path / destination URL
              </label>
              <Input
                value={config.dest_path}
                onChange={(e) => patchConfig({ dest_path: e.target.value })}
                placeholder="/app/backups"
                className="font-mono text-sm"
              />
            </div>

            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={!config.skip_redis}
                  onChange={(e) => patchConfig({ skip_redis: !e.target.checked })}
                  className="h-4 w-4 rounded border-gray-300 text-cisco-blue"
                />
                Include Redis
              </label>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={config.include_volumes}
                  onChange={(e) => patchConfig({ include_volumes: e.target.checked })}
                  className="h-4 w-4 rounded border-gray-300 text-cisco-blue"
                />
                Include Docker volumes
              </label>
            </div>

            <div className="flex justify-end">
              <Button
                size="sm"
                onClick={() => saveConfig.mutate(config)}
                disabled={!configDirty || saveConfig.isPending}
              >
                <Save className="h-4 w-4" />
                {saveConfig.isPending ? 'Saving…' : 'Save Configuration'}
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Delete confirmation modal */}
      <Modal
        open={deleteTarget !== null}
        title="Delete Backup"
        onClose={() => setDeleteTarget(null)}
      >
        <p className="text-sm text-gray-600 dark:text-gray-400">
          Delete backup{' '}
          <span className="font-mono font-medium">{deleteTarget ? fmtTs(deleteTarget) : ''}</span>?
          This cannot be undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={() => setDeleteTarget(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => deleteTarget && deleteBackup.mutate(deleteTarget)}
            disabled={deleteBackup.isPending}
          >
            {deleteBackup.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
