/**
 * Tests for <Badge>.
 *
 * Covers:
 * - Default variant rendering
 * - Each severity variant applies a distinct class
 * - Extra className is merged via twMerge
 * - Children are rendered
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Badge, type BadgeVariant } from './Badge';

describe('<Badge>', () => {
  it('renders children', () => {
    render(<Badge>Critical</Badge>);
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });

  it('uses default variant when none provided', () => {
    const { container } = render(<Badge>Default</Badge>);
    const badge = container.firstChild as HTMLElement;
    expect(badge).toHaveClass('bg-gray-100');
  });

  it('applies critical variant classes', () => {
    const { container } = render(<Badge variant="critical">Crit</Badge>);
    expect(container.firstChild).toHaveClass('bg-red-100');
  });

  it('applies major variant classes', () => {
    const { container } = render(<Badge variant="major">Maj</Badge>);
    expect(container.firstChild).toHaveClass('bg-orange-100');
  });

  it('applies warning variant classes', () => {
    const { container } = render(<Badge variant="warning">Warn</Badge>);
    expect(container.firstChild).toHaveClass('bg-yellow-100');
  });

  it('applies info variant classes', () => {
    const { container } = render(<Badge variant="info">Info</Badge>);
    expect(container.firstChild).toHaveClass('bg-blue-100');
  });

  it('applies success variant classes', () => {
    const { container } = render(<Badge variant="success">OK</Badge>);
    expect(container.firstChild).toHaveClass('bg-green-100');
    expect(container.firstChild).toHaveClass('text-green-700');
  });

  it('applies danger variant classes', () => {
    const { container } = render(<Badge variant="danger">Err</Badge>);
    expect(container.firstChild).toHaveClass('bg-red-100');
  });

  it('applies neutral variant classes', () => {
    const { container } = render(<Badge variant="neutral">Neutral</Badge>);
    expect(container.firstChild).toHaveClass('bg-gray-200');
  });

  it('merges extra className via twMerge', () => {
    const { container } = render(<Badge className="font-bold">Custom</Badge>);
    expect(container.firstChild).toHaveClass('font-bold');
  });

  it('renders as a span element', () => {
    const { container } = render(<Badge>Span</Badge>);
    expect(container.firstChild?.nodeName).toBe('SPAN');
  });

  const severities: BadgeVariant[] = ['critical', 'major', 'minor', 'warning', 'info', 'clear'];
  severities.forEach((v) => {
    it(`renders variant="${v}" without error`, () => {
      render(<Badge variant={v}>{v}</Badge>);
      expect(screen.getByText(v)).toBeInTheDocument();
    });
  });
});
