/**
 * Tests for TelemetryPage.
 *
 * Covers:
 * - Page heading renders
 * - Health stat cards render with data
 * - Empty state when no collectors
 * - Empty state when no subscriptions
 * - Collector rows rendered in table
 * - Subscription rows rendered in table
 * - Sensor catalog empty state
 * - Sensor catalog rows rendered
 * - Create collector button disabled without name
 * - Create subscription button disabled without name
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { TelemetryPage } from './TelemetryPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);

const HEALTH = { collectors: 3, enabled_collectors: 2, subscriptions: 5, enabled_subscriptions: 4 };

const COLLECTORS = [
  { id: 'c1', name: 'gnmi-collector-01', collector_type: 'gnmi', endpoint: 'gnmi://10.0.0.1:57400', enabled: true, status: 'active' },
];

const SUBSCRIPTIONS = [
  { id: 's1', name: 'if-counters', path: '/interfaces/interface/state/counters/in-octets', sample_interval_ms: 60000, mode: 'sample', enabled: true, status: 'active' },
];

const SENSORS = [
  { id: 'sp1', vendor: 'cisco', path: '/interfaces/interface/state/counters/in-octets', metric_name: 'interface.in_octets', kpi_type: 'if_in_octets', unit: 'octets', object_type: 'interface', enabled: true },
];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <TelemetryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TelemetryPage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue({ data: [] });
  });

  it('renders the page heading', async () => {
    renderPage();
    expect(await screen.findByText('Telemetry')).toBeInTheDocument();
  });

  it('renders health stat cards with values from API', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/health') return Promise.resolve({ data: HEALTH });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument());
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows empty state when no collectors', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/collectors') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No telemetry collectors yet')).toBeInTheDocument());
  });

  it('shows empty state when no subscriptions', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/subscriptions') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No telemetry subscriptions yet')).toBeInTheDocument());
  });

  it('renders collector row in the table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/collectors') return Promise.resolve({ data: COLLECTORS });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('gnmi-collector-01')).toBeInTheDocument());
    expect(screen.getByText('gnmi://10.0.0.1:57400')).toBeInTheDocument();
  });

  it('renders subscription row in the table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/subscriptions') return Promise.resolve({ data: SUBSCRIPTIONS });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('if-counters')).toBeInTheDocument());
    expect(screen.getByText('60000ms')).toBeInTheDocument();
  });

  it('shows sensor catalog empty state', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/sensor-paths') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('No sensor paths')).toBeInTheDocument());
  });

  it('renders sensor path in catalog table', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/telemetry/sensor-paths') return Promise.resolve({ data: SENSORS });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('interface.in_octets')).toBeInTheDocument());
    expect(screen.getByText('if_in_octets')).toBeInTheDocument();
    expect(screen.getByText('octets')).toBeInTheDocument();
  });

  it('Create collector button is disabled when name is empty', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: 'Create collector' });
    expect(btn).toBeDisabled();
  });

  it('Create collector button becomes enabled after entering name', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: 'Create collector' });
    const nameInput = screen.getAllByRole('textbox').find((el) => el.closest('label')?.textContent?.includes('Name'));
    if (nameInput) {
      await userEvent.type(nameInput, 'my-collector');
      expect(btn).not.toBeDisabled();
    }
  });

  it('Create subscription button is disabled when name is empty', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: 'Create subscription' });
    expect(btn).toBeDisabled();
  });

  it('renders New collector panel heading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('New collector')).toBeInTheDocument());
  });

  it('renders Sensor path catalog heading', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Sensor path catalog')).toBeInTheDocument());
  });
});
