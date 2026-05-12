import { type ReactNode } from 'react';
import { Card } from './Card';
import { twMerge } from 'tailwind-merge';

interface StatCardProps {
  title?: string;
  label?: string;
  value: string | number;
  icon?: ReactNode;
  trend?: string;
  trendUp?: boolean;
  colorClass?: string;
  loading?: boolean;
  tone?: 'default' | 'success' | 'warning' | 'danger' | string;
}

export function StatCard({ title, label, value, icon, trend, trendUp, colorClass, loading, tone }: StatCardProps) {
  const displayTitle = title ?? label ?? '';
  const toneClass =
    colorClass ??
    (tone === 'success'
      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
      : tone === 'warning'
        ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300'
        : tone === 'danger'
          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
          : 'bg-cisco-blue/10 text-cisco-blue');
  return (
    <Card className="flex items-center gap-4">
      {icon && (
        <div
          className={twMerge(
            'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg',
            toneClass,
          )}
        >
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {displayTitle}
        </p>
        <p className="mt-0.5 text-2xl font-bold text-gray-900 dark:text-gray-100">{loading ? '—' : value}</p>
        {trend && (
          <p
            className={twMerge(
              'text-xs',
              trendUp ? 'text-severity-clear' : 'text-severity-critical',
            )}
          >
            {trend}
          </p>
        )}
      </div>
    </Card>
  );
}
