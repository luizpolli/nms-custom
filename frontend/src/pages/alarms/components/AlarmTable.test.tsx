/**
 * Tests for <AlarmTable>.
 *
 * Covers:
 * - Renders column headers
 * - Renders alarm rows with severity badges
 * - Shows empty state when no alarms
 * - Row checkbox selects / deselects an alarm
 * - "Select all" checkbox selects all visible alarms
 * - Deselect all via "Select all" unchecked
 * - View / Ack / Clear / Suppress / Unsuppress action buttons fire correct callbacks
 * - Columns hidden when not in visibleColumns set
 * - Acknowledged alarm does not show Acknowledge button
 * - Suppressed alarm shows Unsuppress instead of Suppress
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AlarmTable, type Alarm, type AlarmColumnKey } from './AlarmTable';

const makeAlarm = (overrides: Partial<Alarm> = {}): Alarm => ({
  id: 'alarm-1',
  severity: 'critical',
  state: 'active',
  source_host: 'router-core-01',
  event_type: 'linkDown',
  message: 'Interface GigE0/0 is down',
  first_seen: '2025-01-01T10:00:00Z',
  last_seen: '2025-01-01T10:05:00Z',
  occurrence_count: 3,
  ...overrides,
});

const defaultProps = {
  alarms: [],
  selectedIds: new Set<string>(),
  onSelectionChange: vi.fn(),
  onView: vi.fn(),
  onAck: vi.fn(),
  onClear: vi.fn(),
  onSuppress: vi.fn(),
  onUnsuppress: vi.fn(),
};

describe('<AlarmTable>', () => {
  it('renders column headers by default', () => {
    render(<AlarmTable {...defaultProps} />);
    expect(screen.getByText('Severity')).toBeInTheDocument();
    expect(screen.getByText('Device')).toBeInTheDocument();
    expect(screen.getByText('Message')).toBeInTheDocument();
  });

  it('shows empty message when no alarms', () => {
    render(<AlarmTable {...defaultProps} alarms={[]} />);
    expect(screen.getByText('No alarms.')).toBeInTheDocument();
  });

  it('renders a row for each alarm', () => {
    const alarms = [
      makeAlarm({ id: 'a1', source_host: 'router-01' }),
      makeAlarm({ id: 'a2', source_host: 'switch-02' }),
    ];
    render(<AlarmTable {...defaultProps} alarms={alarms} />);
    expect(screen.getByText('router-01')).toBeInTheDocument();
    expect(screen.getByText('switch-02')).toBeInTheDocument();
  });

  it('renders severity badge for each alarm', () => {
    const alarms = [makeAlarm({ severity: 'critical' }), makeAlarm({ id: 'a2', severity: 'major' })];
    render(<AlarmTable {...defaultProps} alarms={alarms} />);
    expect(screen.getAllByText('critical').length).toBeGreaterThan(0);
    expect(screen.getByText('major')).toBeInTheDocument();
  });

  it('renders message text', () => {
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm()]} />);
    expect(screen.getByText('Interface GigE0/0 is down')).toBeInTheDocument();
  });

  it('fires onView when View is clicked', async () => {
    const onView = vi.fn();
    const alarm = makeAlarm();
    render(<AlarmTable {...defaultProps} alarms={[alarm]} onView={onView} />);
    await userEvent.click(screen.getByRole('button', { name: 'View' }));
    expect(onView).toHaveBeenCalledWith(alarm);
  });

  it('fires onAck when Acknowledge is clicked for active alarm', async () => {
    const onAck = vi.fn();
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm({ state: 'active' })]} onAck={onAck} />);
    await userEvent.click(screen.getByRole('button', { name: 'Acknowledge' }));
    expect(onAck).toHaveBeenCalledWith('alarm-1');
  });

  it('does not show Acknowledge button for acknowledged alarm', () => {
    render(
      <AlarmTable
        {...defaultProps}
        alarms={[makeAlarm({ state: 'acknowledged' })]}
      />,
    );
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
  });

  it('shows Unsuppress instead of Suppress for suppressed alarms', () => {
    render(
      <AlarmTable {...defaultProps} alarms={[makeAlarm({ state: 'suppressed' })]} />,
    );
    expect(screen.getByRole('button', { name: 'Unsuppress' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Suppress' })).not.toBeInTheDocument();
  });

  it('fires onClear when Clear is clicked', async () => {
    const onClear = vi.fn();
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm()]} onClear={onClear} />);
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
    expect(onClear).toHaveBeenCalledWith('alarm-1');
  });

  it('fires onSuppress when Suppress is clicked', async () => {
    const onSuppress = vi.fn();
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm()]} onSuppress={onSuppress} />);
    await userEvent.click(screen.getByRole('button', { name: 'Suppress' }));
    expect(onSuppress).toHaveBeenCalledWith('alarm-1');
  });

  it('fires onUnsuppress when Unsuppress is clicked', async () => {
    const onUnsuppress = vi.fn();
    render(
      <AlarmTable
        {...defaultProps}
        alarms={[makeAlarm({ state: 'suppressed' })]}
        onUnsuppress={onUnsuppress}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Unsuppress' }));
    expect(onUnsuppress).toHaveBeenCalledWith('alarm-1');
  });

  it('selects an alarm when its checkbox is checked', async () => {
    const onSelectionChange = vi.fn();
    render(
      <AlarmTable
        {...defaultProps}
        alarms={[makeAlarm()]}
        onSelectionChange={onSelectionChange}
      />,
    );
    const rowCheckbox = screen.getByRole('checkbox', { name: /select alarm alarm-1/i });
    await userEvent.click(rowCheckbox);
    expect(onSelectionChange).toHaveBeenCalledWith(new Set(['alarm-1']));
  });

  it('selects all alarms with the header checkbox', async () => {
    const onSelectionChange = vi.fn();
    const alarms = [makeAlarm({ id: 'a1' }), makeAlarm({ id: 'a2' })];
    render(
      <AlarmTable
        {...defaultProps}
        alarms={alarms}
        onSelectionChange={onSelectionChange}
      />,
    );
    const selectAll = screen.getByRole('checkbox', { name: /select all/i });
    await userEvent.click(selectAll);
    expect(onSelectionChange).toHaveBeenCalledWith(new Set(['a1', 'a2']));
  });

  it('deselects all when selectAll is unchecked while all selected', async () => {
    const onSelectionChange = vi.fn();
    const alarms = [makeAlarm({ id: 'a1' }), makeAlarm({ id: 'a2' })];
    render(
      <AlarmTable
        {...defaultProps}
        alarms={alarms}
        selectedIds={new Set(['a1', 'a2'])}
        onSelectionChange={onSelectionChange}
      />,
    );
    const selectAll = screen.getByRole('checkbox', { name: /select all/i });
    await userEvent.click(selectAll);
    expect(onSelectionChange).toHaveBeenCalledWith(new Set());
  });

  it('hides columns not in visibleColumns', () => {
    const limited = new Set<AlarmColumnKey>(['severity', 'message']);
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm()]} visibleColumns={limited} />);
    expect(screen.queryByText('Device')).not.toBeInTheDocument();
    expect(screen.queryByText('State')).not.toBeInTheDocument();
  });

  it('renders occurrence_count in the row', () => {
    render(<AlarmTable {...defaultProps} alarms={[makeAlarm({ occurrence_count: 7 })]} />);
    expect(screen.getByText('7')).toBeInTheDocument();
  });
});
