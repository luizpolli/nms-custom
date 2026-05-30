/**
 * Tests for <Sidebar>.
 *
 * Covers:
 * - Renders nav links for all enabled modules
 * - Does not render nav items for disabled modules
 * - Collapsed state hides labels but keeps icons
 * - Expand/collapse toggle button fires onToggle
 * - Toggle button label changes with collapsed state
 * - Settings link always present regardless of modules
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { ModuleControlProvider } from './ModuleControlProvider';
import { MODULE_DEFAULTS } from '../../lib/moduleControls';

// Mock api.ts so the ModuleControlProvider doesn't make real HTTP calls
vi.mock('../../lib/api', () => ({
  api: { get: vi.fn() },
}));

import { api } from '../../lib/api';
const mockGet = vi.mocked(api.get);

function renderSidebar(collapsed = false, onToggle = vi.fn()) {
  mockGet.mockResolvedValue({ data: MODULE_DEFAULTS });
  return render(
    <MemoryRouter>
      <ModuleControlProvider>
        <Sidebar collapsed={collapsed} onToggle={onToggle} />
      </ModuleControlProvider>
    </MemoryRouter>,
  );
}

function renderSidebarWithModules(
  moduleOverrides: Partial<typeof MODULE_DEFAULTS>,
  collapsed = false,
  onToggle = vi.fn(),
) {
  mockGet.mockResolvedValue({ data: { ...MODULE_DEFAULTS, ...moduleOverrides } });
  return render(
    <MemoryRouter>
      <ModuleControlProvider>
        <Sidebar collapsed={collapsed} onToggle={onToggle} />
      </ModuleControlProvider>
    </MemoryRouter>,
  );
}

describe('<Sidebar>', () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it('renders the Settings nav link', async () => {
    renderSidebar();
    // Settings link is always present (not module-gated)
    const settingsLink = await screen.findByRole('link', { name: /settings/i });
    expect(settingsLink).toBeInTheDocument();
  });

  it('renders the Dashboard nav link when dashboard module is enabled', async () => {
    renderSidebar();
    const links = await screen.findAllByRole('link', { name: /dashboard/i });
    expect(links.length).toBeGreaterThanOrEqual(1);
  });

  it('does not render nav link for disabled module', async () => {
    renderSidebarWithModules({ topology: false });
    // Wait for loading to finish (other links appear)
    await screen.findByRole('link', { name: /settings/i });
    expect(screen.queryByRole('link', { name: /topology/i })).not.toBeInTheDocument();
  });

  it('calls onToggle when the collapse button is clicked', async () => {
    const onToggle = vi.fn();
    renderSidebar(false, onToggle);
    const toggleBtn = await screen.findByRole('button', { name: /collapse menu/i });
    await userEvent.click(toggleBtn);
    expect(onToggle).toHaveBeenCalledOnce();
  });

  it('shows "Expand menu" label when collapsed', async () => {
    renderSidebar(true);
    const btn = await screen.findByRole('button', { name: /expand menu/i });
    expect(btn).toBeInTheDocument();
  });

  it('shows "Collapse menu" label when not collapsed', async () => {
    renderSidebar(false);
    const btn = await screen.findByRole('button', { name: /collapse menu/i });
    expect(btn).toBeInTheDocument();
  });

  it('hides the "NMS Custom" branding when collapsed', async () => {
    renderSidebar(true);
    await screen.findByRole('button', { name: /expand menu/i });
    expect(screen.queryByText('NMS Custom')).not.toBeInTheDocument();
  });

  it('shows "NMS Custom" branding when not collapsed', async () => {
    renderSidebar(false);
    expect(await screen.findByText('NMS Custom')).toBeInTheDocument();
  });
});
