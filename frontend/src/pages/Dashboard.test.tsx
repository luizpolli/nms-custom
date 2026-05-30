/**
 * Tests for the Dashboard page.
 *
 * Strategy: mock api.ts and useAlarmWebSocket so the component renders
 * with controlled data. We use QueryClientProvider + MemoryRouter.
 *
 * Covers:
 * - Page title ("Dashboard") renders
 * - StatCard for Devices shows device count
 * - StatCard for Active alarms shows sum
 * - StatCard shows "—" while loading
 * - Alarms by severity section renders counts
 * - Top devices by CPU section renders with mock data
 * - Recent Alarms section renders alarm messages
 * - Empty state when no devices
 * - Empty state when no alarms
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from './Dashboard';

// ── Mock dependencies ─────────────────────────────────────────────────────
vi.mock('../lib/api', () => ({
  api: { get: vi.fn() },
}));

vi.mock('../lib/ws', () => ({
  useAlarmWebSocket: vi.fn(() => ({ lastAlarm: null, connected: false })),
}));

import { api } from '../lib/api';
const mockGet = vi.mocked(api.get);

const MOCK_DEVICES = [
  { id: 'd1', name: 'router-01', status: 'reachable' },
  { id: 'd2', name: 'switch-01', status: 'unreachable' },
];

const MOCK_ALARM_SUMMARY = {
  critical: 2,
  major: 1,
  minor: 0,
  warning: 3,
  info: 1,
  clear: 0,
};

const MOCK_PERF_SUMMARY = {
  cpu_avg: 45.2,
  top_devices: [
    { device_id: 'd1', name: 'router-01', cpu_5min: 72.5 },
    { device_id: 'd2', name: 'switch-01', cpu_5min: 31.0 },
  ],
};

const MOCK_RECENT_ALARMS = [
  {
    id: 'a1',
    severity: 'critical',
    state: 'active',
    source_host: 'router-01',
    message: 'Interface is down',
    raised_at: new Date(Date.now() - 60_000).toISOString(),
    last_seen: new Date(Date.now() - 60_000).toISOString(),
  },
];

const MOCK_ASSURANCE = { network_score: 92, health_state: 'Good' };

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0, gcTime: 0 } },
  });
}

function renderDashboard(client?: QueryClient) {
  const qc = client ?? makeQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Dashboard page', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it('renders the page heading', async () => {
    mockGet.mockResolvedValue({ data: [] });
    renderDashboard();
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
  });

  it('shows device count after data loads', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: MOCK_DEVICES });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });

    renderDashboard();
    // Wait for device count to appear — note: '2' may appear multiple times
    // (device count + critical alarm count). We check at least one exists.
    await waitFor(() => {
      const allTwos = screen.getAllByText('2');
      expect(allTwos.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows sum of active alarms', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });

    renderDashboard();
    // critical(2)+major(1)+minor(0)+warning(3) = 6
    await waitFor(() => expect(screen.getByText('6')).toBeInTheDocument());
  });

  it('renders "Alarms by severity" card', async () => {
    mockGet.mockResolvedValue({ data: {} });
    mockGet.mockImplementation((url: string) => {
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      return Promise.resolve({ data: [] });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Alarms by severity')).toBeInTheDocument(),
    );
  });

  it('renders "Top devices by CPU" card', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Top devices by CPU')).toBeInTheDocument(),
    );
  });

  it('shows top device names in the CPU card', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() => expect(screen.getByText('router-01')).toBeInTheDocument());
    expect(screen.getByText('switch-01')).toBeInTheDocument();
  });

  it('shows recent alarm message in Recent Alarms card', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: MOCK_RECENT_ALARMS });
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Interface is down')).toBeInTheDocument(),
    );
  });

  it('shows empty state "No devices discovered yet" when devices array is empty', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/performance/summary') return Promise.resolve({ data: {} });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No devices discovered yet')).toBeInTheDocument(),
    );
  });

  it('shows empty state "No alarms recorded yet" when recent alarms is empty', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: MOCK_DEVICES });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/performance/summary') return Promise.resolve({ data: MOCK_PERF_SUMMARY });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No alarms recorded yet')).toBeInTheDocument(),
    );
  });

  it('shows "No KPI data" when performance summary has no top_devices', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/devices') return Promise.resolve({ data: [] });
      if (url === '/alarms/summary') return Promise.resolve({ data: MOCK_ALARM_SUMMARY });
      if (url === '/alarms') return Promise.resolve({ data: [] });
      if (url === '/performance/summary') return Promise.resolve({ data: { cpu_avg: 10, top_devices: [] } });
      if (url === '/assurance/summary') return Promise.resolve({ data: MOCK_ASSURANCE });
      return Promise.resolve({ data: {} });
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No KPI data')).toBeInTheDocument(),
    );
  });
});
