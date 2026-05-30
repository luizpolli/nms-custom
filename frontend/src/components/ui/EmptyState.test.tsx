/**
 * Tests for <EmptyState>.
 *
 * Covers:
 * - Default render with Inbox icon
 * - title prop renders h3
 * - description / message render helper text
 * - action renders a call-to-action
 * - custom icon overrides default
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState } from './EmptyState';

describe('<EmptyState>', () => {
  it('renders without crashing when no props given', () => {
    const { container } = render(<EmptyState />);
    expect(container).not.toBeEmptyDOMElement();
  });

  it('renders the title as h3', () => {
    render(<EmptyState title="No devices found" />);
    expect(screen.getByRole('heading', { level: 3, name: 'No devices found' })).toBeInTheDocument();
  });

  it('renders description text', () => {
    render(<EmptyState description="Add a device to get started" />);
    expect(screen.getByText('Add a device to get started')).toBeInTheDocument();
  });

  it('renders message as alias for description', () => {
    render(<EmptyState message="No alarms recorded yet" />);
    expect(screen.getByText('No alarms recorded yet')).toBeInTheDocument();
  });

  it('renders an action node', () => {
    render(
      <EmptyState
        title="No data"
        action={<button>Add Device</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'Add Device' })).toBeInTheDocument();
  });

  it('renders a custom icon', () => {
    render(<EmptyState icon={<span data-testid="custom-icon" />} />);
    expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
  });

  it('shows default Inbox icon when icon prop is not provided', () => {
    const { container } = render(<EmptyState />);
    // Inbox from lucide-react renders an SVG
    expect(container.querySelector('svg')).toBeInTheDocument();
  });
});
