/**
 * Tests for <StatCard>.
 *
 * Covers:
 * - Renders value and label
 * - Shows "—" when loading=true
 * - Renders icon
 * - Renders trend text
 * - Applies tone classes (success, warning, danger)
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatCard } from './StatCard';

describe('<StatCard>', () => {
  it('renders the label and value', () => {
    render(<StatCard label="Devices" value={42} />);
    expect(screen.getByText('Devices')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders "—" when loading is true', () => {
    render(<StatCard label="CPU" value="75%" loading />);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('75%')).not.toBeInTheDocument();
  });

  it('renders the icon when provided', () => {
    render(
      <StatCard
        label="Status"
        value={1}
        icon={<span data-testid="stat-icon" />}
      />,
    );
    expect(screen.getByTestId('stat-icon')).toBeInTheDocument();
  });

  it('renders trend text', () => {
    render(<StatCard label="Score" value={95} trend="Healthy" trendUp />);
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });

  it('does not render trend when not provided', () => {
    const { container } = render(<StatCard label="Score" value={95} />);
    // No trend paragraph
    expect(container.querySelectorAll('p').length).toBe(2); // label + value only
  });

  it('applies success tone class to icon wrapper', () => {
    const { container } = render(
      <StatCard
        label="Assurance"
        value={99}
        tone="success"
        icon={<span />}
      />,
    );
    const iconWrapper = container.querySelector('[class*="bg-green-100"]');
    expect(iconWrapper).toBeInTheDocument();
  });

  it('applies warning tone class to icon wrapper', () => {
    const { container } = render(
      <StatCard
        label="Alarms"
        value={5}
        tone="warning"
        icon={<span />}
      />,
    );
    expect(container.querySelector('[class*="bg-yellow-100"]')).toBeInTheDocument();
  });

  it('applies danger tone class to icon wrapper', () => {
    const { container } = render(
      <StatCard
        label="Errors"
        value={10}
        tone="danger"
        icon={<span />}
      />,
    );
    expect(container.querySelector('[class*="bg-red-100"]')).toBeInTheDocument();
  });

  it('renders title prop as alias for label', () => {
    render(<StatCard title="Total Devices" value={100} />);
    expect(screen.getByText('Total Devices')).toBeInTheDocument();
  });

  it('renders value as string', () => {
    render(<StatCard label="CPU" value="45.3%" />);
    expect(screen.getByText('45.3%')).toBeInTheDocument();
  });
});
