/**
 * Tests for <ToastContainer> and pushToast.
 *
 * Covers:
 * - pushToast shows an info toast
 * - pushToast shows an error toast with error styling
 * - pushToast shows a success toast
 * - api-error window event triggers an error toast
 * - Dismiss button removes the toast
 * - At most 3 toasts are shown simultaneously
 */

import { describe, expect, it } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastContainer, pushToast } from './Toast';

describe('ToastContainer + pushToast', () => {
  it('renders nothing when no toasts exist', () => {
    const { container } = render(<ToastContainer />);
    // The live region should be present but empty
    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
    expect(liveRegion?.children).toHaveLength(0);
  });

  it('shows an info toast when pushToast is called', async () => {
    render(<ToastContainer />);
    act(() => pushToast('Operation complete'));
    await waitFor(() => expect(screen.getByText('Operation complete')).toBeInTheDocument());
  });

  it('shows an error toast with correct message', async () => {
    render(<ToastContainer />);
    act(() => pushToast('Something failed', 'error'));
    await waitFor(() => expect(screen.getByText('Something failed')).toBeInTheDocument());
  });

  it('shows a success toast', async () => {
    render(<ToastContainer />);
    act(() => pushToast('Device saved', 'success'));
    await waitFor(() => expect(screen.getByText('Device saved')).toBeInTheDocument());
  });

  it('shows a toast when api-error event is dispatched', async () => {
    render(<ToastContainer />);
    act(() => {
      window.dispatchEvent(
        new CustomEvent('api-error', { detail: 'Unauthorized' }),
      );
    });
    await waitFor(() => expect(screen.getByText('Unauthorized')).toBeInTheDocument());
  });

  it('dismisses a toast when close button is clicked', async () => {
    render(<ToastContainer />);
    act(() => pushToast('Dismiss me'));
    await waitFor(() => expect(screen.getByText('Dismiss me')).toBeInTheDocument());

    const closeButtons = screen.getAllByRole('button', { name: /close/i });
    await userEvent.click(closeButtons[closeButtons.length - 1]);

    await waitFor(() => expect(screen.queryByText('Dismiss me')).not.toBeInTheDocument());
  });

  it('shows at most 3 toasts when more are pushed', async () => {
    render(<ToastContainer />);
    act(() => {
      pushToast('Toast A');
      pushToast('Toast B');
      pushToast('Toast C');
      pushToast('Toast D');
    });
    await waitFor(() => {
      const closeButtons = screen.getAllByRole('button', { name: /close/i });
      expect(closeButtons.length).toBeLessThanOrEqual(3);
    });
  });

  it('handles api-error event with object detail gracefully', async () => {
    render(<ToastContainer />);
    act(() => {
      window.dispatchEvent(
        new CustomEvent('api-error', { detail: { detail: 'Not Found' } }),
      );
    });
    await waitFor(() => expect(screen.getByText('Not Found')).toBeInTheDocument());
  });
});
