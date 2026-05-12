import { type ReactNode } from 'react';
import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  message?: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, description, message, action, icon }: EmptyStateProps) {
  const helper = description ?? message;
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 text-gray-400 dark:text-gray-600">
        {icon ?? <Inbox className="h-12 w-12" />}
      </div>
      {title && <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h3>}
      {helper && (
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{helper}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
