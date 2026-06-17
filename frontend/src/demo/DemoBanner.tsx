import { FlaskConical, X } from 'lucide-react';
import { isDemoEnabled, setDemoMode } from './index';

export function DemoBanner() {
  if (!isDemoEnabled()) return null;

  return (
    <div
      role="alert"
      className="
        fixed top-0 inset-x-0 z-[9999]
        flex items-center justify-between gap-3
        bg-amber-500 px-4 py-2 text-sm font-semibold text-amber-950
        shadow-md
      "
    >
      <span className="flex items-center gap-2">
        <FlaskConical className="h-4 w-4 shrink-0" />
        DEMO MODE — displaying synthetic data. No real devices or alarms.
      </span>
      <button
        onClick={() => setDemoMode(false)}
        aria-label="Exit demo mode"
        className="
          flex items-center gap-1 rounded border border-amber-700/50
          bg-amber-600/30 px-2 py-0.5 text-xs
          hover:bg-amber-700/40 transition-colors
        "
      >
        <X className="h-3 w-3" />
        Exit demo
      </button>
    </div>
  );
}
