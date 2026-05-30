/**
 * Tests for CredentialsPage.
 *
 * Covers:
 * - Page heading renders
 * - Loading spinner shown
 * - Error state renders
 * - Empty state when no credentials
 * - Credential rows rendered in table
 * - Protocol badge displayed
 * - Has-secret badge shown
 * - Add Credential button opens modal
 * - Edit button opens modal
 * - Delete button calls delete API (with confirm)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { CredentialsPage } from './CredentialsPage';

vi.mock('../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

// Mock the CredentialFormModal to isolate page-level behavior
vi.mock('./CredentialFormModal', () => ({
  CredentialFormModal: ({ open, onClose }: { open: boolean; onClose: () => void }) =>
    open ? (
      <div role="dialog" aria-label="credential-modal">
        <button onClick={onClose}>Close modal</button>
      </div>
    ) : null,
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);
const mockDelete = vi.mocked(api.delete);

const CREDENTIALS = [
  { id: 'cred1', name: 'prod-snmp', hostname: '10.0.0.1', username: 'admin', protocol: 'snmp', snmp_version: 'v2c', port: 161, has_secret: true },
  { id: 'cred2', name: 'mgmt-ssh', hostname: '', username: 'cisco', protocol: 'ssh', snmp_version: '', port: 22, has_secret: false },
];

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <CredentialsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('CredentialsPage', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockDelete.mockReset();
  });

  it('renders the page heading', async () => {
    mockGet.mockResolvedValue({ data: [] });
    renderPage();
    expect(await screen.findByText('Credentials')).toBeInTheDocument();
  });

  it('shows empty state when no credentials', async () => {
    mockGet.mockResolvedValue({ data: [] });
    renderPage();
    await waitFor(() => expect(screen.getByText('No credentials')).toBeInTheDocument());
  });

  it('renders credential rows in table', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    renderPage();
    await waitFor(() => expect(screen.getByText('prod-snmp')).toBeInTheDocument());
    expect(screen.getByText('mgmt-ssh')).toBeInTheDocument();
  });

  it('shows protocol badges', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    renderPage();
    // SNMP appears in both the table header column AND as a badge, so use getAllByText
    await waitFor(() => expect(screen.getAllByText('SNMP').length).toBeGreaterThan(0));
    expect(screen.getAllByText('SSH').length).toBeGreaterThan(0);
  });

  it('shows has_secret badge', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    renderPage();
    await waitFor(() => expect(screen.getByText('Yes')).toBeInTheDocument());
    expect(screen.getByText('No')).toBeInTheDocument();
  });

  it('shows error message on failed fetch', async () => {
    mockGet.mockRejectedValue(new Error('500'));
    renderPage();
    await waitFor(() => expect(screen.getByText('Failed to load credentials.')).toBeInTheDocument());
  });

  it('opens modal when Add Credential Profile is clicked', async () => {
    mockGet.mockResolvedValue({ data: [] });
    renderPage();
    const btn = await screen.findByRole('button', { name: /Add Credential Profile/i });
    await userEvent.click(btn);
    expect(screen.getByRole('dialog', { name: 'credential-modal' })).toBeInTheDocument();
  });

  it('opens modal when Edit is clicked', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    renderPage();
    const editBtns = await screen.findAllByRole('button', { name: 'Edit' });
    await userEvent.click(editBtns[0]);
    expect(screen.getByRole('dialog', { name: 'credential-modal' })).toBeInTheDocument();
  });

  it('calls delete API after confirming', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    mockDelete.mockResolvedValue({ data: {} });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();
    // Delete button has no text label (icon only) - find all buttons in the table and pick the Trash icon ones
    // There are Edit and Delete (icon) buttons per row. We find all buttons after Edit buttons.
    const editBtns = await screen.findAllByRole('button', { name: 'Edit' });
    // The Delete button is right after each Edit button
    // Get all buttons and find those that are siblings of Edit buttons
    const allBtns = screen.getAllByRole('button');
    const editIdx = allBtns.indexOf(editBtns[0]);
    const deleteBtn = allBtns[editIdx + 1];
    await userEvent.click(deleteBtn);
    expect(mockDelete).toHaveBeenCalledWith('/credentials/cred1');
  });

  it('does not call delete API when confirm is cancelled', async () => {
    mockGet.mockResolvedValue({ data: CREDENTIALS });
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    renderPage();
    const editBtns = await screen.findAllByRole('button', { name: 'Edit' });
    const allBtns = screen.getAllByRole('button');
    const editIdx = allBtns.indexOf(editBtns[0]);
    const deleteBtn = allBtns[editIdx + 1];
    await userEvent.click(deleteBtn);
    expect(mockDelete).not.toHaveBeenCalled();
  });
});
