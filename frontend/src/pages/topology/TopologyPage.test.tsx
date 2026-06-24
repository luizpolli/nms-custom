/**
 * Tests for TopologyPage.
 *
 * TopologyPage fetches via the shared `api` instance from lib/api.ts, so we
 * mock that module directly — mocking raw 'axios' instead leaves lib/api.ts's
 * real axios.create() call returning an incomplete object (no `interceptors`),
 * which crashes at import time since api.ts wires interceptors eagerly.
 * TopologyGraph uses ReactFlow + dagre; we mock it for speed.
 *
 * Covers:
 * - Page heading renders
 * - Loading state shown while fetching
 * - Error state renders "Failed to load topology"
 * - Empty topology state renders
 * - Renders graph when data has nodes
 * - Legend items shown
 * - Retry button present when error
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import TopologyPage from './TopologyPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

// Mock TopologyGraph to avoid ReactFlow/dagre/canvas issues in tests
vi.mock('./components/TopologyGraph', () => ({
  TopologyGraph: ({ nodes }: { nodes: Array<{ id: string; label: string }> }) => (
    <div data-testid="topology-graph">
      {nodes.map((n) => (
        <span key={n.id}>{n.label}</span>
      ))}
    </div>
  ),
}));

// Mock RebuildButton to keep tests focused on the page
vi.mock('./components/RebuildButton', () => ({
  RebuildButton: ({ onSuccess }: { onSuccess: () => void }) => (
    <button onClick={onSuccess} data-testid="rebuild-btn">
      Rebuild all
    </button>
  ),
}));

import { api } from '../../lib/api';
const mockAxiosGet = vi.mocked(api.get);

const NODES = [
  { id: 'n1', label: 'router-core-01', vendor: 'cisco', role: 'core' },
  { id: 'n2', label: 'switch-edge-01', vendor: 'cisco', role: 'edge' },
];
const LINKS = [{ source: 'n1', target: 'n2', source_iface: 'Gi0/0', target_iface: 'Gi1/0' }];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <TopologyPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TopologyPage', () => {
  beforeEach(() => {
    mockAxiosGet.mockReset();
  });

  it('renders the page heading', async () => {
    mockAxiosGet.mockResolvedValue({ data: { nodes: [], links: [] } });
    renderPage();
    expect(await screen.findByText('Network Topology')).toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    // Never resolves during this test
    mockAxiosGet.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading topology...')).toBeInTheDocument();
  });

  it('shows error state on failed fetch', async () => {
    mockAxiosGet.mockRejectedValue(new Error('Network error'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Failed to load topology')).toBeInTheDocument());
  });

  it('shows retry button on error', async () => {
    mockAxiosGet.mockRejectedValue(new Error('oops'));
    renderPage();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument());
  });

  it('shows empty topology message when no nodes', async () => {
    mockAxiosGet.mockResolvedValue({ data: { nodes: [], links: [] } });
    renderPage();
    await waitFor(() => expect(screen.getByText('No devices in topology')).toBeInTheDocument());
  });

  it('renders legend labels', async () => {
    mockAxiosGet.mockResolvedValue({ data: { nodes: [], links: [] } });
    renderPage();
    await waitFor(() => expect(screen.getByText('Cisco')).toBeInTheDocument());
    expect(screen.getByText('Juniper')).toBeInTheDocument();
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('renders the topology graph when nodes exist', async () => {
    mockAxiosGet.mockResolvedValue({ data: { nodes: NODES, links: LINKS } });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('topology-graph')).toBeInTheDocument());
    expect(screen.getByText('router-core-01')).toBeInTheDocument();
    expect(screen.getByText('switch-edge-01')).toBeInTheDocument();
  });

  it('rebuild button is visible', async () => {
    mockAxiosGet.mockResolvedValue({ data: { nodes: [], links: [] } });
    renderPage();
    expect(await screen.findByTestId('rebuild-btn')).toBeInTheDocument();
  });
});
