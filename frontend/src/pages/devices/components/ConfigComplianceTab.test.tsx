/**
 * Tests for <ConfigComplianceTab>.
 *
 * Covers:
 * - Drift badge per status (in_sync / drift / no_golden)
 * - Drift diff rendering with added/removed counts
 * - Collect backup posts and reports dedupe
 * - Set-as-golden only offered for backup rows and posts the backup id
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigComplianceTab, type ConfigBackupMeta, type ConfigDrift } from './ConfigComplianceTab';
import { api } from '../../../lib/api';

vi.mock('../../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

const mockedApi = vi.mocked(api);

const _BACKUP: ConfigBackupMeta = {
  id: 'b-1',
  kind: 'backup',
  contentHash: 'a'.repeat(64),
  sizeBytes: 2048,
  collectedBy: 'api-key',
  createdAt: '2026-06-12T10:00:00Z',
};

const _GOLDEN: ConfigBackupMeta = { ..._BACKUP, id: 'g-1', kind: 'golden' };

function mockQueries(drift: ConfigDrift, backups: ConfigBackupMeta[]) {
  mockedApi.get.mockImplementation((url: string) => {
    if (url.endsWith('/config-drift')) return Promise.resolve({ data: drift });
    return Promise.resolve({ data: backups });
  });
}

function renderTab() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfigComplianceTab deviceId="dev-1" />
    </QueryClientProvider>,
  );
}

describe('<ConfigComplianceTab>', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows in-sync badge when no drift', async () => {
    mockQueries(
      { status: 'in_sync', goldenId: 'g-1', backupId: 'b-1', diff: '', added: 0, removed: 0 },
      [_GOLDEN, _BACKUP],
    );
    renderTab();
    expect(await screen.findByText('In sync')).toBeInTheDocument();
  });

  it('shows drift badge, counts, and the diff', async () => {
    mockQueries(
      {
        status: 'drift',
        goldenId: 'g-1',
        backupId: 'b-1',
        diff: '--- golden\n+++ backup\n@@ -1 +1 @@\n- no shutdown\n+ shutdown',
        added: 1,
        removed: 1,
      },
      [_GOLDEN, _BACKUP],
    );
    renderTab();
    expect(await screen.findByText('Drift detected')).toBeInTheDocument();
    expect(screen.getByText('+1 / -1 lines vs golden')).toBeInTheDocument();
    expect(screen.getByText('+ shutdown')).toBeInTheDocument();
  });

  it('prompts to promote a golden when none is set', async () => {
    mockQueries(
      { status: 'no_golden', goldenId: null, backupId: 'b-1', diff: '', added: 0, removed: 0 },
      [_BACKUP],
    );
    renderTab();
    expect(await screen.findByText('No golden config')).toBeInTheDocument();
    expect(screen.getByText(/promote a backup below/i)).toBeInTheDocument();
  });

  it('collects a backup and reports dedupe', async () => {
    mockQueries(
      { status: 'no_golden', goldenId: null, backupId: 'b-1', diff: '', added: 0, removed: 0 },
      [_BACKUP],
    );
    mockedApi.post.mockResolvedValue({ data: { ..._BACKUP, deduplicated: true } });
    renderTab();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /collect backup now/i }));

    expect(mockedApi.post).toHaveBeenCalledWith('/devices/dev-1/config-backups');
    expect(await screen.findByText(/deduplicated/i)).toBeInTheDocument();
  });

  it('offers set-as-golden only for backup rows and posts the id', async () => {
    mockQueries(
      { status: 'no_golden', goldenId: null, backupId: 'b-1', diff: '', added: 0, removed: 0 },
      [_GOLDEN, _BACKUP],
    );
    mockedApi.post.mockResolvedValue({ data: { ..._GOLDEN } });
    renderTab();
    const user = userEvent.setup();

    const buttons = await screen.findAllByRole('button', { name: /set as golden/i });
    expect(buttons).toHaveLength(1); // golden row has no button

    await user.click(buttons[0]);
    expect(mockedApi.post).toHaveBeenCalledWith('/devices/dev-1/golden-config', {
      backup_id: 'b-1',
    });
  });
});
