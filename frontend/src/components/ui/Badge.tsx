import { type ReactNode } from 'react';
import { twMerge } from 'tailwind-merge';
import { clsx } from 'clsx';
import type { AlarmSeverity } from '../../lib/types';

export type BadgeVariant = AlarmSeverity | 'default' | 'success' | 'neutral' | 'danger';

const variantClasses: Record<BadgeVariant, string> = {
  critical: 'bg-red-100 text-severity-critical dark:bg-red-900/30',
  major: 'bg-orange-100 text-severity-major dark:bg-orange-900/30',
  minor: 'bg-amber-100 text-severity-minor dark:bg-amber-900/30',
  warning: 'bg-yellow-100 text-severity-warning dark:bg-yellow-900/30',
  info: 'bg-blue-100 text-severity-info dark:bg-blue-900/30',
  clear: 'bg-green-100 text-severity-clear dark:bg-green-900/30',
  default: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  success: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  danger: 'bg-red-100 text-severity-critical dark:bg-red-900/30',
  neutral: 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
};

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  return (
    <span
      className={twMerge(
        clsx(
          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
          variantClasses[variant],
        ),
        className,
      )}
    >
      {children}
    </span>
  );
}
