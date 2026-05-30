/**
 * Tests for <Input>.
 *
 * Covers:
 * - Renders without label/error
 * - Renders label linked to the input via htmlFor
 * - Shows error text and applies error class
 * - Shows hint text when no error
 * - Forwards ref
 * - Accepts typing
 * - Disabled state
 */

import { createRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Input } from './Input';

describe('<Input>', () => {
  it('renders a text input by default', () => {
    render(<Input />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('renders the label and links it to the input', () => {
    render(<Input label="IP Address" />);
    const label = screen.getByText('IP Address');
    const input = screen.getByRole('textbox');
    expect(label).toBeInTheDocument();
    expect(input).toHaveAttribute('id', 'ip-address');
  });

  it('shows error text', () => {
    render(<Input error="Required" />);
    expect(screen.getByText('Required')).toBeInTheDocument();
  });

  it('applies error class when error provided', () => {
    render(<Input error="Bad value" />);
    expect(screen.getByRole('textbox')).toHaveClass('border-severity-critical');
  });

  it('shows hint text when no error', () => {
    render(<Input hint="Enter CIDR notation" />);
    expect(screen.getByText('Enter CIDR notation')).toBeInTheDocument();
  });

  it('does not show hint when error is present', () => {
    render(<Input hint="Hint text" error="Error text" />);
    expect(screen.queryByText('Hint text')).not.toBeInTheDocument();
    expect(screen.getByText('Error text')).toBeInTheDocument();
  });

  it('forwards ref to the underlying <input>', () => {
    const ref = createRef<HTMLInputElement>();
    render(<Input ref={ref} />);
    expect(ref.current).toBeInstanceOf(HTMLInputElement);
  });

  it('accepts user typing', async () => {
    render(<Input />);
    const input = screen.getByRole('textbox');
    await userEvent.type(input, '192.168.1.1');
    expect(input).toHaveValue('192.168.1.1');
  });

  it('is disabled when disabled prop is set', () => {
    render(<Input disabled />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });

  it('passes through placeholder', () => {
    render(<Input placeholder="e.g. 10.0.0.1" />);
    expect(screen.getByPlaceholderText('e.g. 10.0.0.1')).toBeInTheDocument();
  });

  it('fires onChange', async () => {
    const onChange = vi.fn();
    render(<Input onChange={onChange} />);
    await userEvent.type(screen.getByRole('textbox'), 'x');
    expect(onChange).toHaveBeenCalled();
  });
});
