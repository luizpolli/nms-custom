import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { RefreshCw, RotateCcw } from 'lucide-react';
import { Badge, Button, Card, Spinner } from '../../components/ui';
import { api } from '../../lib/api';

type ContainerState = 'running' | 'exited' | 'restarting' | 'paused' | 'dead' | 'unknown';

type ContainerInfo = {
  name: string;
  label: string;
  group: string;
  critical: boolean;
  state: ContainerState;
  status_text: string;
};

type ContainersResponse = {
  docker_available: boolean;
  containers: ContainerInfo[];
};

const STATE_BADGE: Record<string, { variant: 'success' | 'warning' | 'danger' | 'default'; text: string }> = {
  running:    { variant: 'success', text: 'Running' },
  restarting: { variant: 'warning', text: 'Restarting' },
  exited:     { variant: 'danger',  text: 'Stopped' },
  dead:       { variant: 'danger',  text: 'Dead' },
  paused:     { variant: 'warning', text: 'Paused' },
  unknown:    { variant: 'default', text: 'Unknown' },
};

const GROUPS = ['Infrastructure', 'Application', 'Workers', 'Receivers'];

export function ContainersPanel() {
  const qc = useQueryClient();

  const { data, isLoading, isFetching } = useQuery<ContainersResponse>({
    queryKey: ['system', 'containers'],
    queryFn: () => api.get('/system/containers').then((r) => r.data),
    refetchInterval: 30_000,
  });

  const restart = useMutation({
    mutationFn: (name: string) => api.post(`/system/containers/${name}/restart`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['system', 'containers'] }),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner />
      </div>
    );
  }

  const containers = data?.containers ?? [];
  const byGroup = Object.fromEntries(
    GROUPS.map((g) => [g, containers.filter((c) => c.group === g)]),
  );

  return (
    <div className="space-y-6">
      {/* Docker availability banner */}
      {data && !data.docker_available && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          Docker CLI not available inside this container. Mount the Docker socket
          (<code className="font-mono text-xs">/var/run/docker.sock</code>) to enable
          container actions and live status.
        </div>
      )}

      {/* Refresh */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {containers.filter((c) => c.state === 'running').length} of {containers.length} containers running
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => qc.invalidateQueries({ queryKey: ['system', 'containers'] })}
          disabled={isFetching}
        >
          <RefreshCw className={['h-4 w-4', isFetching ? 'animate-spin' : ''].join(' ')} />
          Refresh
        </Button>
      </div>

      {/* Groups */}
      {GROUPS.map((group) => {
        const items = byGroup[group] ?? [];
        if (!items.length) return null;
        return (
          <Card key={group}>
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">{group}</h3>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {items.map((c) => {
                const badge = STATE_BADGE[c.state] ?? STATE_BADGE.unknown;
                return (
                  <div key={c.name} className="flex items-center justify-between px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {c.label}
                        {c.critical && (
                          <span className="ml-2 text-xs text-gray-400 dark:text-gray-500">critical</span>
                        )}
                      </p>
                      <p className="text-xs text-gray-400 font-mono dark:text-gray-500">{c.name}</p>
                      {c.status_text !== '—' && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{c.status_text}</p>
                      )}
                    </div>
                    <div className="ml-4 flex items-center gap-3 shrink-0">
                      <Badge variant={badge.variant}>{badge.text}</Badge>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => restart.mutate(c.name)}
                        disabled={!data?.docker_available || restart.isPending}
                        title="Restart container"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
