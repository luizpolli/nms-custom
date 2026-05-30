/**
 * Tests for <AlarmSummaryStrip>.
 *
 * Covers:
 * - Renders all 6 severity buttons
 * - Renders counts from summary prop
 * - onSelect fires with the correct severity key
 * - Active severity applies a ring class
 * - No onSelect → buttons are disabled
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AlarmSummaryStrip } from './AlarmSummaryStrip';

const SUMMARY = {
  critical: 5,
  major: 3,
  minor: 1,
  warning: 2,
  info: 0,
  clear: 0,
};

describe('<AlarmSummaryStrip>', () => {
  it('renders all 6 severity buttons', () => {
    render(<AlarmSummaryStrip summary={SUMMARY} />);
    for (const label of ['Critical', 'Major', 'Minor', 'Warning', 'Info', 'Clear']) {
      expect(screen.getByRole('button', { name: new RegExp(label, 'i') })).toBeInTheDocument();
    }
  });

  it('renders the critical count', () => {
    render(<AlarmSummaryStrip summary={SUMMARY} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders the major count', () => {
    render(<AlarmSummaryStrip summary={SUMMARY} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('calls onSelect with "critical" when Critical button is clicked', async () => {
    const onSelect = vi.fn();
    render(<AlarmSummaryStrip summary={SUMMARY} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', { name: /critical/i }));
    expect(onSelect).toHaveBeenCalledWith('critical');
  });

  it('calls onSelect with "warning" when Warning is clicked', async () => {
    const onSelect = vi.fn();
    render(<AlarmSummaryStrip summary={SUMMARY} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole('button', { name: /warning/i }));
    expect(onSelect).toHaveBeenCalledWith('warning');
  });

  it('does not call onSelect when no handler provided', async () => {
    // Buttons are disabled without onSelect
    render(<AlarmSummaryStrip summary={SUMMARY} />);
    const critBtn = screen.getByRole('button', { name: /critical/i });
    expect(critBtn).toBeDisabled();
  });

  it('applies ring class for active severity', () => {
    render(
      <AlarmSummaryStrip summary={SUMMARY} activeSeverity="major" onSelect={vi.fn()} />,
    );
    const majorBtn = screen.getByRole('button', { name: /major/i });
    expect(majorBtn).toHaveClass('ring-2');
  });

  it('does not apply ring class to non-active severities', () => {
    render(
      <AlarmSummaryStrip summary={SUMMARY} activeSeverity="major" onSelect={vi.fn()} />,
    );
    const critBtn = screen.getByRole('button', { name: /critical/i });
    expect(critBtn).not.toHaveClass('ring-2');
  });

  it('renders zero count for severities with no alarms', () => {
    render(<AlarmSummaryStrip summary={{ critical: 0, major: 0, minor: 0, warning: 0, info: 0 }} />);
    const zeroCounts = screen.getAllByText('0');
    expect(zeroCounts.length).toBeGreaterThanOrEqual(5);
  });
});
