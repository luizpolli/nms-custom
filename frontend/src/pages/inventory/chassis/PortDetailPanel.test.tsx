/**
 * Tests for <PortDetailPanel> port control.
 *
 * Covers:
 * - Enable/Disable buttons render only when an interface is bound
 * - Disable flow asks for confirmation and posts the admin-status request
 * - Cancel aborts without calling the API
 * - 403 responses surface a permission message
 * - extractAdminStatusError fallbacks
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PortDetailPanel, extractAdminStatusError } from './PortDetailPanel';
import { api } from '../../../lib/api';

vi.mock('../../../lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

const mockedApi = vi.mocked(api);

function portDetail(withInterface = true) {
  return {
    deviceId: 'dev-1',
    physicalIndex: 301,
    component: { physicalIndex: 301, name: 'GigabitEthernet0/0/0' },
    interface: withInterface
      ? {
          id: 'iface-1',
          name: 'GigabitEthernet0/0/0',
          adminStatus: 'up',
          operStatus: 'up',
        }
      : null,
    alarms: [],
  };
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PortDetailPanel deviceId="dev-1" physicalIndex={301} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('<PortDetailPanel> port control', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows Enable/Disable buttons when an interface is bound', async () => {
    mockedApi.get.mockResolvedValue({ data: portDetail() });
    renderPanel();
    expect(await screen.findByRole('button', { name: /enable/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /disable/i })).toBeInTheDocument();
  });

  it('hides port control when no interface is bound', async () => {
    mockedApi.get.mockResolvedValue({ data: portDetail(false) });
    renderPanel();
    expect(await screen.findByText(/no managed interface matched/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /disable/i })).not.toBeInTheDocument();
  });

  it('confirms and posts a disable request', async () => {
    mockedApi.get.mockResolvedValue({ data: portDetail() });
    mockedApi.post.mockResolvedValue({
      data: {
        interfaceName: 'GigabitEthernet0/0/0',
        action: 'disable',
        success: true,
        adminStatus: 'down',
      },
    });
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /disable/i }));
    expect(screen.getByText(/shutdown/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /confirm/i }));

    expect(mockedApi.post).toHaveBeenCalledWith(
      '/devices/dev-1/interfaces/iface-1/admin-status',
      { action: 'disable' },
    );
    expect(await screen.findByText(/disabled/i)).toBeInTheDocument();
  });

  it('cancel aborts without calling the API', async () => {
    mockedApi.get.mockResolvedValue({ data: portDetail() });
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /enable/i }));
    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(mockedApi.post).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: /enable/i })).toBeInTheDocument();
  });

  it('surfaces a permission message on 403', async () => {
    mockedApi.get.mockResolvedValue({ data: portDetail() });
    mockedApi.post.mockRejectedValue({ response: { status: 403, data: { detail: 'nope' } } });
    renderPanel();
    const user = userEvent.setup();

    await user.click(await screen.findByRole('button', { name: /enable/i }));
    await user.click(screen.getByRole('button', { name: /confirm/i }));

    expect(await screen.findByText(/admin role required/i)).toBeInTheDocument();
  });
});

describe('extractAdminStatusError', () => {
  it('prefers the 403 message', () => {
    expect(extractAdminStatusError({ response: { status: 403 } })).toMatch(/admin role/i);
  });

  it('falls back to the API detail string', () => {
    expect(
      extractAdminStatusError({ response: { status: 422, data: { detail: 'no credential' } } }),
    ).toBe('no credential');
  });

  it('returns a generic message otherwise', () => {
    expect(extractAdminStatusError(new Error('boom'))).toBe('Request failed.');
  });
});
