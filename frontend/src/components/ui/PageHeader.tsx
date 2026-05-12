import { type ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  description?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, subtitle, actions }: PageHeaderProps) {
  const helper = description ?? subtitle;
  return (
    <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">{title}</h1>
        {helper && (
          <p className="text-sm text-gray-500 dark:text-gray-400">{helper}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
