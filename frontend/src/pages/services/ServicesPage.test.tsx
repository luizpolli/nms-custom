/**
 * Tests for ServicesPage.
 *
 * Covers:
 * - Page heading renders
 * - Stat cards render with service counts
 * - Empty state when no services
 * - Service row rendered in impact matrix
 * - Create service modal opens
 * - Create button disabled when no name
 * - Dependency graph empty state
 * - Service alerts section shown when alerts exist
 * - Service card rendered for each service
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ServicesPage } from './ServicesPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);

const SERVICES = [
  {
    id: 'svc1',
    name: 'Core Transport',
    kind: 'transport',
    description: 'Core backbone',
    target_score: 95,
    member_count: 3,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    members: [],
    dependencies: [],
  },
  {
    id: 'svc2',
    name: 'Customer MPLS',
    kind: 'customer',
    description: null,
    target_score: null,
    member_count: 1,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
    members: [],
    dependencies: [],
  },
];

const IMPACT = [
  { service_id: 'svc1', name: 'Core Transport', kind: 'transport', score: 98, base_score: 100, dependency_penalty: 0, health_state: 'Good', member_count: 3, impacted_member_count: 0, active_alarm_count: 0, worst_severity: 'info', members: [], dependency_impacts: [] },
];

const ALERTS = [
  { service_id: 'svc2', name: 'Customer MPLS', kind: 'customer', score: 72, target_score: 90, deficit: 18, health_state: 'Degraded', worst_severity: 'major', impacted_member_count: 1, active_alarm_count: 2 },
];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <ServicesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ServicesPage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue({ data: [] });
  });

  it('renders the page heading', async () => {
    renderPage();
    expect(await screen.findByText('Services')).toBeInTheDocument();
  });

  it('renders stat cards when services load', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/services') return Promise.resolve({ data: SERVICES });
      if (url === '/assurance/services') return Promise.resolve({ data: IMPACT });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText('Services modeled')).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('2')).toBeInTheDocument());
  });

  it('shows empty state when no services', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('No services modeled')).toBeInTheDocument());
  });

  it('renders dependency graph empty state', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText('No dependency edges')).toBeInTheDocument());
  });

  it('renders service names in the impact matrix', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/services') return Promise.resolve({ data: SERVICES });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getAllByText('Core Transport').length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.getAllByText('Customer MPLS').length).toBeGreaterThan(0));
  });

  it('shows service alerts section when alerts exist', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/assurance/service-alerts') return Promise.resolve({ data: ALERTS });
      if (url === '/services') return Promise.resolve({ data: SERVICES });
      return Promise.resolve({ data: [] });
    });
    renderPage();
    await waitFor(() => expect(screen.getByText(/below target threshold/i)).toBeInTheDocument());
  });

  it('opens create service modal when button clicked', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: /create service/i });
    await userEvent.click(btn);
    await waitFor(() => expect(screen.getAllByRole('dialog').length).toBeGreaterThan(0));
  });

  it('Create button in modal is disabled when name is empty', async () => {
    renderPage();
    const btn = await screen.findByRole('button', { name: /create service/i });
    await userEvent.click(btn);
    const submitBtn = await screen.findByRole('button', { name: /^create$/i });
    expect(submitBtn).toBeDisabled();
  });

  it('Create button enables after entering a service name', async () => {
    renderPage();
    const openBtn = await screen.findByRole('button', { name: /create service/i });
    await userEvent.click(openBtn);
    const nameInput = await screen.findByRole('textbox', { name: /^name$/i });
    await userEvent.type(nameInput, 'My new service');
    const submitBtn = screen.getByRole('button', { name: /^create$/i });
    expect(submitBtn).not.toBeDisabled();
  });
});
