/**
 * Tests for <DeviceStatusBadge>.
 *
 * Covers:
 * - Each known status maps to a human label
 * - Unknown status falls back to the raw string
 * - Variant classes are applied correctly
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DeviceStatusBadge } from './DeviceStatusBadge';

describe('<DeviceStatusBadge>', () => {
  it('renders "Reachable" for reachable status', () => {
    render(<DeviceStatusBadge status="reachable" />);
    expect(screen.getByText('Reachable')).toBeInTheDocument();
  });

  it('renders "Unreachable" for unreachable status', () => {
    render(<DeviceStatusBadge status="unreachable" />);
    expect(screen.getByText('Unreachable')).toBeInTheDocument();
  });

  it('renders "Unknown" for unknown status', () => {
    render(<DeviceStatusBadge status="unknown" />);
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('renders "Polling" for polling status', () => {
    render(<DeviceStatusBadge status="polling" />);
    expect(screen.getByText('Polling')).toBeInTheDocument();
  });

  it('renders raw status string for unrecognized statuses', () => {
    render(<DeviceStatusBadge status="maintenance" />);
    expect(screen.getByText('maintenance')).toBeInTheDocument();
  });

  it('applies success variant for reachable', () => {
    const { container } = render(<DeviceStatusBadge status="reachable" />);
    expect(container.firstChild).toHaveClass('bg-green-100');
  });

  it('applies danger variant for unreachable', () => {
    const { container } = render(<DeviceStatusBadge status="unreachable" />);
    expect(container.firstChild).toHaveClass('bg-red-100');
  });

  it('applies warning variant for unknown', () => {
    const { container } = render(<DeviceStatusBadge status="unknown" />);
    expect(container.firstChild).toHaveClass('bg-yellow-100');
  });
});
