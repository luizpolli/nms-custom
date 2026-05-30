/**
 * Tests for AssurancePage.
 *
 * Covers:
 * - Page heading renders
 * - Stat cards render with summary data
 * - Empty state for root-cause groups
 * - Root-cause groups rendered
 * - Empty state for impacted devices
 * - Impacted device names rendered
 * - Empty state for services
 * - Empty state for event timeline
 * - Network score value shown
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AssurancePage } from './AssurancePage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);

const SUMMARY = {
  network_score: 87,
  health_state: 'Degraded',
  active_alarm_count: 5,
  active_group_count: 2,
  impacted_device_count: 1,
  impacted_interface_count: 3,
  baseline_breach_count: 0,
  top_impacted_devices: [
    { name: 'router-core-01', score: 74, active_alarms: 3, worst_severity: 'critical', last_seen: null },
  ],
  top_impacted_interfaces: [],
  top_groups: [
    {
      group_key: 'link-down-core',
      root_cause: 'linkDown',
      severity: 'critical',
      category: 'link',
      state: 'active',
      active_count: 3,
      occurrence_count: 3,
      impacted_devices: ['router-core-01'],
      first_seen: '2025-01-01T09:00:00Z',
      last_seen: '2025-01-01T10:00:00Z',
    },
  ],
};

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <AssurancePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AssurancePage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue({ data: [] });
  });

  it('renders the page heading', async () => {
    renderPage();
    expect(await screen.findByText('Assurance')).toBeInTheDocument();
  });

  it('renders network score stat card', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/summary') return Promise.resolve({ data: SUMMARY });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('87').length).toBeGreaterThan(0));
  });

  it('renders health state from summary', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/summary') return Promise.resolve({ data: SUMMARY });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('Degraded').length).toBeGreaterThan(0));
  });

  it('shows empty state for root-cause groups when none', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/summary') return Promise.resolve({ data: { ...SUMMARY, top_groups: [] } });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No active groups')).toBeInTheDocument());
  });

  it('renders root-cause group row when data present', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/summary') return Promise.resolve({ data: SUMMARY });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    // group_key is used as React key but not rendered; the visible fields are root_cause and category
    await waitFor(() => expect(screen.getAllByText('linkDown').length).toBeGreaterThan(0));
  });

  it('renders impacted device name', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/summary') return Promise.resolve({ data: SUMMARY });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('router-core-01').length).toBeGreaterThan(0));
  });

  it('shows empty state for services when none', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/services') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No services modeled')).toBeInTheDocument());
  });

  it('shows empty state for event timeline when empty', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('No recent events')).toBeInTheDocument());
  });

  it('shows empty state for topology impact', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/impact') return Promise.resolve({ data: { root: null, impacted_nodes: [], impacted_count: 0, max_depth: 0 } });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No topology impact')).toBeInTheDocument());
  });

  it('renders stat cards headings', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Network score')).toBeInTheDocument());
    expect(screen.getByText('Health state')).toBeInTheDocument();
    expect(screen.getByText('Active groups')).toBeInTheDocument();
  });
});
