/**
 * Tests for <Select>.
 *
 * Covers:
 * - Renders without props
 * - Renders label linked to select element
 * - Renders options from the options prop
 * - Renders custom children (manual <option> elements)
 * - Shows error text and applies error class
 * - Forwards ref to the <select> element
 * - Fires onChange on user interaction
 * - Disabled state
 */

import { createRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Select } from './Select';

describe('<Select>', () => {
  it('renders a select element', () => {
    render(<Select />);
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders label and links to select', () => {
    render(<Select label="Severity" />);
    expect(screen.getByText('Severity')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toHaveAttribute('id', 'severity');
  });

  it('renders options from options prop', () => {
    render(
      <Select
        options={[
          { value: 'critical', label: 'Critical' },
          { value: 'major', label: 'Major' },
        ]}
      />,
    );
    expect(screen.getByRole('option', { name: 'Critical' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Major' })).toBeInTheDocument();
  });

  it('renders children options', () => {
    render(
      <Select>
        <option value="all">All</option>
        <option value="active">Active</option>
      </Select>,
    );
    expect(screen.getByRole('option', { name: 'All' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Active' })).toBeInTheDocument();
  });

  it('shows error text', () => {
    render(<Select error="Selection required" />);
    expect(screen.getByText('Selection required')).toBeInTheDocument();
  });

  it('applies error class when error provided', () => {
    render(<Select error="Bad" />);
    expect(screen.getByRole('combobox')).toHaveClass('border-severity-critical');
  });

  it('forwards ref to the <select> element', () => {
    const ref = createRef<HTMLSelectElement>();
    render(<Select ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLSelectElement);
  });

  it('fires onChange when selection changes', async () => {
    const onChange = vi.fn();
    render(
      <Select
        onChange={onChange}
        options={[
          { value: 'a', label: 'Option A' },
          { value: 'b', label: 'Option B' },
        ]}
      />,
    );
    await userEvent.selectOptions(screen.getByRole('combobox'), 'b');
    expect(onChange).toHaveBeenCalled();
  });

  it('is disabled when disabled prop is set', () => {
    render(<Select disabled />);
    expect(screen.getByRole('combobox')).toBeDisabled();
  });
});
