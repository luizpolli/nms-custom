/**
 * Tests for <Modal>.
 *
 * Covers:
 * - Returns null when open=false
 * - Renders title and children when open=true
 * - Close button calls onClose
 * - Backdrop click calls onClose
 * - Escape key calls onClose
 * - Size classes are applied
 * - role="dialog" and aria-modal are present
 */

import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from './Modal';

describe('<Modal>', () => {
  it('renders nothing when open=false', () => {
    const { container } = render(
      <Modal open={false} onClose={vi.fn()} title="Test">
        content
      </Modal>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the title when open=true', () => {
    render(
      <Modal open onClose={vi.fn()} title="Device Details">
        inner
      </Modal>,
    );
    expect(screen.getByText('Device Details')).toBeInTheDocument();
  });

  it('renders children content', () => {
    render(
      <Modal open onClose={vi.fn()} title="T">
        <p>Hello world</p>
      </Modal>,
    );
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('has role="dialog" and aria-modal="true"', () => {
    render(
      <Modal open onClose={vi.fn()} title="T">
        x
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });

  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        x
      </Modal>,
    );
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        x
      </Modal>,
    );
    // The backdrop is the aria-hidden div behind the dialog
    const backdrop = document.querySelector('[aria-hidden="true"]') as HTMLElement;
    await userEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        x
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('does not fire Escape listener when closed', () => {
    const onClose = vi.fn();
    render(
      <Modal open={false} onClose={onClose} title="T">
        x
      </Modal>,
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).not.toHaveBeenCalled();
  });

  it('applies the correct max-w class for size=lg', () => {
    render(
      <Modal open onClose={vi.fn()} title="T" size="lg">
        x
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveClass('max-w-lg');
  });

  it('applies max-w-2xl for size=xl', () => {
    render(
      <Modal open onClose={vi.fn()} title="T" size="xl">
        x
      </Modal>,
    );
    expect(screen.getByRole('dialog')).toHaveClass('max-w-2xl');
  });
});
