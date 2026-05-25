import { useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

interface PageIntroFloatProps {
  title: string;
  icon?: ReactNode;
  children: ReactNode;
  onDismiss: (options: { dontShowAgain: boolean }) => void;
  dismissPreferenceLabel?: string;
  showDismissPreference?: boolean;
}

export function PageIntroFloat({
  title,
  icon,
  children,
  onDismiss,
  dismissPreferenceLabel = 'Do not show again',
  showDismissPreference = true,
}: PageIntroFloatProps) {
  const [dontShowAgain, setDontShowAgain] = useState(false);
  if (typeof document === 'undefined') return null;

  const handleDismiss = () => onDismiss({ dontShowAgain });

  return createPortal(
    <div
      className="fixed left-1/2 top-1/2 z-[9999] max-h-[min(80vh,42rem)] w-[min(42rem,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-cisco-blue/20 bg-white p-4 text-sm shadow-2xl dark:border-cisco-blue/40 dark:bg-gray-900"
      role="dialog"
      aria-label={title}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2 font-semibold text-gray-900 dark:text-white">
          {icon}
          <span>{title}</span>
        </div>
        <button
          type="button"
          className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          aria-label={`Dismiss ${title}`}
          onClick={handleDismiss}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {children}
      {showDismissPreference && (
        <label className="mt-4 flex items-center gap-2 border-t border-gray-200 pt-3 text-xs text-gray-500 dark:border-gray-700 dark:text-gray-400">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300 text-cisco-blue focus:ring-cisco-blue"
            checked={dontShowAgain}
            onChange={(event) => setDontShowAgain(event.target.checked)}
          />
          <span>{dismissPreferenceLabel}</span>
        </label>
      )}
    </div>,
    document.body,
  );
}
