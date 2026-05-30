/**
 * Tests for <Spinner> and <SpinnerOverlay>.
 *
 * Covers:
 * - Renders an SVG with role="status"
 * - Size prop applies correct h/w classes
 * - SpinnerOverlay renders a Spinner
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Spinner, SpinnerOverlay } from './Spinner';

describe('<Spinner>', () => {
  it('renders an svg with role="status"', () => {
    render(<Spinner />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has accessible label', () => {
    render(<Spinner />);
    expect(screen.getByLabelText('Loading...')).toBeInTheDocument();
  });

  it('applies md size by default', () => {
    render(<Spinner />);
    expect(screen.getByRole('status')).toHaveClass('h-8', 'w-8');
  });

  it('applies sm size class', () => {
    render(<Spinner size="sm" />);
    expect(screen.getByRole('status')).toHaveClass('h-4', 'w-4');
  });

  it('applies lg size class', () => {
    render(<Spinner size="lg" />);
    expect(screen.getByRole('status')).toHaveClass('h-12', 'w-12');
  });

  it('merges custom className', () => {
    render(<Spinner className="text-red-500" />);
    expect(screen.getByRole('status')).toHaveClass('text-red-500');
  });
});

describe('<SpinnerOverlay>', () => {
  it('renders a spinner inside a flex container', () => {
    render(<SpinnerOverlay />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
