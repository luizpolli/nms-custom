import { type ReactNode } from 'react';
import { Card } from './Card';
import { twMerge } from 'tailwind-merge';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: ReactNode;
  trend?: string;
  trendUp?: boolean;
  colorClass?: string;
}

export function StatCard({ title, value, icon, trend, trendUp, colorClass }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4">
      {icon && (
        <div
          className={twMerge(
            'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg',
            colorClass ?? 'bg-cisco-blue/10 text-cisco-blue',
          )}
        >
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {title}
        </p>
        <p className="mt-0.5 text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
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
