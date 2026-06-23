import { twMerge } from 'tailwind-merge';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  className?: string;
}

/** Binary on/off toggle — the shared replacement for raw `<input type="checkbox">` enable/disable controls. */
export function Switch({ checked, onChange, disabled, label, className }: SwitchProps) {
  return (
    <label className={twMerge('inline-flex items-center gap-2 text-sm', disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer', className)}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={twMerge(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-cisco-blue-light focus-visible:ring-offset-1',
          checked ? 'bg-cisco-blue' : 'bg-gray-300 dark:bg-gray-600',
          disabled ? 'cursor-not-allowed' : 'cursor-pointer',
        )}
      >
        <span
          className={twMerge(
            'inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-[18px]' : 'translate-x-1',
          )}
        />
      </button>
      {label && <span>{label}</span>}
    </label>
  );
}
