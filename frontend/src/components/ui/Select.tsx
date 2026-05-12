import { type SelectHTMLAttributes, type ReactNode, forwardRef } from 'react';
import { twMerge } from 'tailwind-merge';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string;
  error?: string;
  options?: SelectOption[];
  children?: ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, children, className, id, ...rest }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={selectId} className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={twMerge(
            'rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900',
            'focus:outline-none focus:ring-2 focus:ring-cisco-blue focus:border-transparent',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100',
            error && 'border-severity-critical',
            className,
          )}
          {...rest}
        >
          {options
            ? options.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100">
                  {opt.label}
                </option>
              ))
            : children}
        </select>
        {error && <p className="text-xs text-severity-critical">{error}</p>}
      </div>
    );
  },
);

Select.displayName = 'Select';
