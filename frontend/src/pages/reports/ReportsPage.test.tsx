/**
 * Tests for ReportsPage.
 *
 * ReportsPage uses axios directly (not api.ts).
 *
 * Covers:
 * - Heading renders
 * - Loading state shown
 * - "No reports available" empty state
 * - Report cards rendered for each available report
 * - Format badges rendered
 * - Report card selection
 * - Generate button is visible when report selected
 * - Generate button triggers POST
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ReportsPage from './ReportsPage';

vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    create: vi.fn(() => ({ get: vi.fn(), post: vi.fn() })),
  },
  get: vi.fn(),
  post: vi.fn(),
}));

// Mock the download utilities to avoid file system side effects
vi.mock('./lib/download', () => ({
  downloadBlob: vi.fn(),
  extractFilename: vi.fn(() => 'report.xlsx'),
  formatExtFromFormat: vi.fn((fmt: string) => fmt),
}));

// Mock the ReportParamsForm to keep tests focused
vi.mock('./components/ReportParamsForm', () => ({
  ReportParamsForm: () => <div data-testid="report-params-form">Params form</div>,
}));

import axios from 'axios';
const mockAxiosGet = vi.mocked(axios.get);
const mockAxiosPost = vi.mocked(axios.post);

const AVAILABLE_REPORTS = [
  { name: 'device_inventory', format: 'excel', description: 'All discovered devices' },
  { name: 'alarm_history', format: 'pdf', description: 'Historical alarm data' },
  { name: 'performance_kpi', format: 'xlsx', description: 'KPI metrics export' },
];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ReportsPage', () => {
  beforeEach(() => {
    mockAxiosGet.mockReset();
    mockAxiosPost.mockReset();
  });

  it('renders the page heading', async () => {
    mockAxiosGet.mockResolvedValue({ data: [] });
    renderPage();
    expect(await screen.findByText('Reports')).toBeInTheDocument();
  });

  it('shows loading text while fetching', () => {
    mockAxiosGet.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('shows "No reports available" when list is empty', async () => {
    mockAxiosGet.mockResolvedValue({ data: [] });
    renderPage();
    await waitFor(() => expect(screen.getByText('No reports available')).toBeInTheDocument());
  });

  it('renders report cards for each available report', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    renderPage();
    await waitFor(() => expect(screen.getByText('device_inventory')).toBeInTheDocument());
    expect(screen.getByText('alarm_history')).toBeInTheDocument();
    expect(screen.getByText('performance_kpi')).toBeInTheDocument();
  });

  it('renders format badges', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('EXCEL').length).toBeGreaterThan(0));
    // PDF appears as both a group header and badge, so use getAllByText
    await waitFor(() => expect(screen.getAllByText('PDF').length).toBeGreaterThan(0));
  });

  it('renders report description text', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    renderPage();
    await waitFor(() => expect(screen.getByText('All discovered devices')).toBeInTheDocument());
  });

  it('shows generate button after selecting a report', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    renderPage();
    const reportCard = await screen.findByText('device_inventory');
    await userEvent.click(reportCard);
    expect(await screen.findByRole('button', { name: /generate/i })).toBeInTheDocument();
  });

  it('calls POST to generate when generate button clicked', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    mockAxiosPost.mockResolvedValue({ data: new Blob(['data']), headers: {} });
    renderPage();
    const reportCard = await screen.findByText('device_inventory');
    await userEvent.click(reportCard);
    const genBtn = await screen.findByRole('button', { name: /generate/i });
    await userEvent.click(genBtn);
    await waitFor(() => expect(mockAxiosPost).toHaveBeenCalledWith(
      '/api/reports/generate',
      expect.objectContaining({ name: 'device_inventory' }),
      expect.any(Object),
    ));
  });

  it('groups reports by format', async () => {
    mockAxiosGet.mockResolvedValue({ data: AVAILABLE_REPORTS });
    renderPage();
    await waitFor(() => {
      // Excel group header should appear
      expect(screen.getByText('Excel')).toBeInTheDocument();
      // PDF appears as both section header and badge
      expect(screen.getAllByText('PDF').length).toBeGreaterThan(0);
    });
  });
});
