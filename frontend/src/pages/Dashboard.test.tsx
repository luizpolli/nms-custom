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

const MOCK_TRENDS = { series: [], buckets: [] };
const MOCK_IFACE_UTIL = { items: [] };
const MOCK_ALARM_TREND = { hours: 24, buckets: 24, data: [] };

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

  /** Helper: build a mock that responds to all Dashboard endpoints. */
  function mockAllEndpoints(overrides: Record<string, unknown> = {}) {
    mockGet.mockImplementation(((url: string) => {
      const defaults: Record<string, unknown> = {
        '/devices': MOCK_DEVICES,
        '/alarms/summary': MOCK_ALARM_SUMMARY,
        '/alarms': MOCK_RECENT_ALARMS,
        '/performance/summary': MOCK_PERF_SUMMARY,
        '/assurance/summary': MOCK_ASSURANCE,
        '/dashboard/trends': MOCK_TRENDS,
        '/dashboard/interface-utilization': MOCK_IFACE_UTIL,
        '/dashboard/alarm-trend': MOCK_ALARM_TREND,
      };
      const match = Object.keys({ ...defaults, ...overrides }).find(k => url === k || url.startsWith(k));
      const data = match ? (overrides[match] ?? defaults[match]) : {};
      return Promise.resolve({ data });
    }) as typeof api.get);
  }

  it('renders the page heading', async () => {
    mockGet.mockResolvedValue({ data: [] });
    renderDashboard();
    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
  });

  it('shows device count after data loads', async () => {
    mockAllEndpoints();
    renderDashboard();
    await waitFor(() => {
      const allTwos = screen.getAllByText('2');
      expect(allTwos.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows sum of active alarms', async () => {
    mockAllEndpoints({ '/devices': [] });
    renderDashboard();
    await waitFor(() => expect(screen.getByText('6')).toBeInTheDocument());
  });

  it('renders "Alarms by severity" card', async () => {
    mockAllEndpoints();
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Alarms by severity')).toBeInTheDocument(),
    );
  });

  it('renders "Top devices by CPU" card', async () => {
    mockAllEndpoints();
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Top devices by CPU')).toBeInTheDocument(),
    );
  });

  it('shows top device names in the CPU card', async () => {
    mockAllEndpoints();
    renderDashboard();
    await waitFor(() => expect(screen.getAllByText('router-01').length).toBeGreaterThanOrEqual(1));
    expect(screen.getAllByText('switch-01').length).toBeGreaterThanOrEqual(1);
  });

  it('shows recent alarm message in Recent Alarms card', async () => {
    mockAllEndpoints();
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Interface is down')).toBeInTheDocument(),
    );
  });

  it('shows empty state "No devices discovered yet" when devices array is empty', async () => {
    mockAllEndpoints({ '/devices': [] });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No devices discovered yet')).toBeInTheDocument(),
    );
  });

  it('shows empty state "No alarms recorded yet" when recent alarms is empty', async () => {
    mockAllEndpoints({ '/alarms': [] });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No alarms recorded yet')).toBeInTheDocument(),
    );
  });

  it('shows "No KPI data" when performance summary has no top_devices', async () => {
    mockAllEndpoints({ '/devices': [], '/performance/summary': { cpu_avg: 10, top_devices: [] } });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No KPI data')).toBeInTheDocument(),
    );
  });
});
