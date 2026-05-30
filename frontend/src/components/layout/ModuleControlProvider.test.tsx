/**
 * Tests for <ModuleControlProvider> and useModuleControls.
 *
 * Covers:
 * - Provides default MODULE_DEFAULTS when API call succeeds
 * - isEnabled returns true for enabled modules, false for disabled
 * - moduleLabel returns the human label for a key
 * - nms-modules-updated event updates module state
 * - loading state transitions correctly
 * - Throws when used outside provider
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { ModuleControlProvider, useModuleControls } from './ModuleControlProvider';
import { MODULE_DEFAULTS } from '../../lib/moduleControls';

// ── Mock api.ts ────────────────────────────────────────────────────────────
vi.mock('../../lib/api', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);

// ── Helper component ────────────────────────────────────────────────────────
function Probe({ moduleKey }: { moduleKey: keyof typeof MODULE_DEFAULTS }) {
  const { isEnabled, moduleLabel, loading } = useModuleControls();
  if (loading) return <div>loading...</div>;
  return (
    <div>
      <span data-testid="enabled">{isEnabled(moduleKey) ? 'yes' : 'no'}</span>
      <span data-testid="label">{moduleLabel(moduleKey)}</span>
    </div>
  );
}

describe('ModuleControlProvider', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state initially', () => {
    // Never resolves so we see loading
    mockGet.mockReturnValue(new Promise(() => {}));
    render(
      <ModuleControlProvider>
        <Probe moduleKey="alarms" />
      </ModuleControlProvider>,
    );
    expect(screen.getByText('loading...')).toBeInTheDocument();
  });

  it('renders modules after successful fetch', async () => {
    mockGet.mockResolvedValue({ data: MODULE_DEFAULTS });
    render(
      <ModuleControlProvider>
        <Probe moduleKey="alarms" />
      </ModuleControlProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('enabled')).toBeInTheDocument());
    expect(screen.getByTestId('enabled').textContent).toBe('yes');
  });

  it('uses MODULE_DEFAULTS when the API call fails', async () => {
    mockGet.mockRejectedValue(new Error('Network error'));
    render(
      <ModuleControlProvider>
        <Probe moduleKey="alarms" />
      </ModuleControlProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('enabled').textContent).toBe('yes'));
  });

  it('isEnabled returns false for a disabled module', async () => {
    mockGet.mockResolvedValue({
      data: { ...MODULE_DEFAULTS, alarms: false },
    });
    render(
      <ModuleControlProvider>
        <Probe moduleKey="alarms" />
      </ModuleControlProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('enabled').textContent).toBe('no'));
  });

  it('moduleLabel returns the correct label', async () => {
    mockGet.mockResolvedValue({ data: MODULE_DEFAULTS });
    render(
      <ModuleControlProvider>
        <Probe moduleKey="devices" />
      </ModuleControlProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('label').textContent).toBe('Devices'));
  });

  it('updates when nms-modules-updated event fires', async () => {
    mockGet.mockResolvedValue({ data: MODULE_DEFAULTS });
    render(
      <ModuleControlProvider>
        <Probe moduleKey="topology" />
      </ModuleControlProvider>,
    );
    await waitFor(() => expect(screen.getByTestId('enabled').textContent).toBe('yes'));

    // Disable topology via event
    act(() => {
      window.dispatchEvent(
        new CustomEvent('nms-modules-updated', {
          detail: { ...MODULE_DEFAULTS, topology: false },
        }),
      );
    });

    await waitFor(() => expect(screen.getByTestId('enabled').textContent).toBe('no'));
  });

  it('throws when useModuleControls is used outside provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const BadConsumer = () => {
      useModuleControls();
      return null;
    };
    expect(() => render(<BadConsumer />)).toThrow(
      'useModuleControls must be used inside ModuleControlProvider',
    );
    consoleError.mockRestore();
  });
});
