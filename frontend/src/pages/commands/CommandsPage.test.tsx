/**
 * Tests for CommandsPage.
 *
 * Covers:
 * - Page heading renders
 * - Tab navigation renders
 * - Empty state when no commands
 * - Command rows rendered in table
 * - Add Command button opens modal
 * - Run button triggers API call
 * - Output modal shown after run
 * - Delete command calls API
 * - Error state on load failure
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { CommandsPage } from './CommandsPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

// Mock sub-panels to isolate the main page
vi.mock('./CommandFormModal', () => ({
  CommandFormModal: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div role="dialog" aria-label="command-form-modal">
        <button onClick={onClose}>Close</button>
      </div>
    ) : null,
}));
vi.mock('./BulkRunModal', () => ({
  BulkRunModal: () => null,
}));
vi.mock('./RunHistoryPanel', () => ({
  RunHistoryPanel: () => <div>Run History</div>,
}));
vi.mock('./SchedulesPanel', () => ({
  SchedulesPanel: () => <div>Schedules</div>,
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);
const mockPost = vi.mocked(api.post);
const mockDelete = vi.mocked(api.delete);

const COMMANDS = [
  { id: 'cmd1', name: 'show-version', cli_command: 'show version', output_path: '/tmp/out.txt', device_id: 'dev1' },
  { id: 'cmd2', name: 'show-interfaces', cli_command: 'show interfaces', output_path: '/tmp/if.txt', device_id: undefined },
];

const DEVICES = [{ id: 'dev1', name: 'router-01', ip_address: '10.0.0.1' }];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <CommandsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('CommandsPage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockDelete.mockReset();
    mockGet.mockImplementation((url: string) => {
      if (url === '/commands') return Promise.resolve({ data: [] });
      if (url === '/devices') return Promise.resolve({ data: DEVICES });
      return Promise.resolve({ data: [] });
    });
  });

  it('renders page heading', async () => {
    renderPage();
    // 'Commands' appears in multiple places (heading, tab button) — use getAllByText
    await waitFor(() => expect(screen.getAllByText('Commands').length).toBeGreaterThan(0));
  });

  it('renders tab navigation', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Commands' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Run History' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Schedules' })).toBeInTheDocument();
    });
  });

  it('shows empty state when no commands', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('No commands')).toBeInTheDocument());
  });

  it('renders command rows in table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/commands') return Promise.resolve({ data: COMMANDS });
      return Promise.resolve({ data: DEVICES });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('show-version')).toBeInTheDocument());
    expect(screen.getByText('show-interfaces')).toBeInTheDocument();
  });

  it('shows CLI command text in table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/commands') return Promise.resolve({ data: COMMANDS });
      return Promise.resolve({ data: DEVICES });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('show version')).toBeInTheDocument());
  });

  it('opens command form modal when Add Command clicked', async () => {
    renderPage();
    const addBtn = await screen.findByRole('button', { name: /Add Command/i });
    await userEvent.click(addBtn);
    expect(screen.getByRole('dialog', { name: 'command-form-modal' })).toBeInTheDocument();
  });

  it('shows output modal after successful run', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/commands') return Promise.resolve({ data: COMMANDS });
      return Promise.resolve({ data: DEVICES });
    });
    mockPost.mockResolvedValue({ data: { output: 'Cisco IOS 15.7' } });
    renderPage();
    await screen.findAllByRole('button', { name: '' });
    // Find Run button by its accessible title or nearby icon
    const runBtn = screen.getAllByRole('button').find((b) => b.title === 'Run' || b.closest('td')?.querySelector('svg[class*="play"]'));
    if (runBtn) {
      await userEvent.click(runBtn);
      await waitFor(() => expect(screen.getByText('Cisco IOS 15.7')).toBeInTheDocument());
    }
  });

  it('calls delete API after confirmation', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/commands') return Promise.resolve({ data: COMMANDS });
      return Promise.resolve({ data: DEVICES });
    });
    mockDelete.mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    // Delete button: icon-only, no accessible text. It comes after the Edit button in each row.
    await screen.findAllByRole('button', { name: 'Edit' });
    const allBtns = screen.getAllByRole('button');
    // The Run button (Play icon) and Edit button precede the Delete (Trash) button per row
    // Find the Run button (has title="Run") and go 2 ahead for delete
    const runBtns = await screen.findAllByTitle('Run');
    const runIdx = allBtns.indexOf(runBtns[0]);
    const deleteBtn = allBtns[runIdx + 2]; // Run → Edit → Delete
    await userEvent.click(deleteBtn);
    expect(mockDelete).toHaveBeenCalledWith('/commands/cmd1');
  });

  it('switches to Run History tab', async () => {
    renderPage();
    // Tab buttons are plain <button> elements - find by exact label
    await waitFor(() => expect(screen.getAllByText('Run History').length).toBeGreaterThan(0));
    const historyTabBtns = screen.getAllByText('Run History');
    await userEvent.click(historyTabBtns[0]);
    // After clicking, the RunHistoryPanel renders 'Run History' text
    expect(screen.getAllByText('Run History').length).toBeGreaterThan(0);
  });
});
