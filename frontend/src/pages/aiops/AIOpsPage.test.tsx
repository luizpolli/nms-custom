/**
 * Tests for AIOpsPage.
 *
 * Covers:
 * - Page heading renders
 * - Advisory-only banner renders
 * - Advisory cards render headings
 * - Advisory loading state
 * - Advisory error shows "No data" empty state
 * - Advisory data rendered (title + summary)
 * - Citations list
 * - Assistant panel renders
 * - Ask button disabled when input empty
 * - 503 disabled state renders
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AIOpsPage } from './AIOpsPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);
const mockPost = vi.mocked(api.post);

const ADVISORY = {
  advisory_type: 'alarm_summary',
  title: 'Critical link-down group detected',
  summary: 'Three link-down alarms on core routers over the last hour.',
  recommendations: ['Check fiber for router-core-01', 'Validate BGP sessions'],
  citations: [
    { source_type: 'alarm', object_id: 'a1', label: 'linkDown on Gi0/0', timestamp: '2025-01-01T10:00:00Z', detail: 'Interface GigE down' },
  ],
  advisory_only: true,
  generated_at: '2025-01-01T10:05:00Z',
};

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <AIOpsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AIOpsPage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    // Default all advisory endpoints to error (so empty state shows)
    mockGet.mockRejectedValue(new Error('no data'));
  });

  it('renders the page heading', async () => {
    renderPage();
    expect(await screen.findByText('AI Ops')).toBeInTheDocument();
  });

  it('renders advisory-only warning banner', async () => {
    renderPage();
    // The banner contains the text 'advisory-only' across elements; use getAllByText
    await waitFor(() => {
      const matches = screen.getAllByText(/advisory.only/i);
      expect(matches.length).toBeGreaterThan(0);
    });
  });

  it('renders advisory card headings', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('Alarm group summary')).toBeInTheDocument());
    expect(screen.getByText('KPI anomaly explanation')).toBeInTheDocument();
    expect(screen.getByText('Runbook suggestions')).toBeInTheDocument();
    expect(screen.getByText('Report narrative')).toBeInTheDocument();
  });

  it('shows "No data" empty state on advisory error', async () => {
    renderPage();
    // With all advisory queries failing, at least one "No data" empty state should appear
    // Note: loading state shows first, then error state after
    await waitFor(
      () => {
        const noDataElements = screen.getAllByText('No data');
        expect(noDataElements.length).toBeGreaterThan(0);
      },
      { timeout: 5000 },
    );
  });

  it('renders advisory title and summary when data loads', async () => {
    mockGet.mockResolvedValue({ data: ADVISORY });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('Critical link-down group detected').length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.getAllByText(/Three link-down alarms/i).length).toBeGreaterThan(0));
  });

  it('renders recommendations when advisory loads', async () => {
    mockGet.mockResolvedValue({ data: ADVISORY });
    renderPage();
    await waitFor(() => expect(screen.getAllByText(/Check fiber for router-core-01/i).length).toBeGreaterThan(0));
  });

  it('renders citations when advisory loads', async () => {
    mockGet.mockResolvedValue({ data: ADVISORY });
    renderPage();
    await waitFor(() => expect(screen.getAllByText(/linkDown on Gi0\/0/i).length).toBeGreaterThan(0));
  });

  it('renders AI Ops assistant panel', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText(/AI Ops assistant/i)).toBeInTheDocument());
  });

  it('Ask button is disabled when question input is empty', async () => {
    renderPage();
    const askBtn = await screen.findByRole('button', { name: 'Ask' });
    expect(askBtn).toBeDisabled();
  });

  it('Ask button enables after typing a question', async () => {
    renderPage();
    const input = await screen.findByPlaceholderText(/what is happening/i);
    await userEvent.type(input, 'What is wrong with the core router?');
    const askBtn = screen.getByRole('button', { name: 'Ask' });
    expect(askBtn).not.toBeDisabled();
  });

  it('shows 503 disabled state when backend returns 503', async () => {
    const err503 = Object.assign(new Error('Service Unavailable'), { response: { status: 503 } });
    mockPost.mockRejectedValue(err503);

    renderPage();
    const input = await screen.findByPlaceholderText(/what is happening/i);
    await userEvent.type(input, 'Is the network ok?');
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }));
    await waitFor(() => expect(screen.getByText('Assistant disabled')).toBeInTheDocument());
  });
});
