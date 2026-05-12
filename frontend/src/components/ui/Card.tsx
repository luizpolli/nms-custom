import { type ReactNode, type HTMLAttributes } from 'react';
import { twMerge } from 'tailwind-merge';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: boolean;
}

export function Card({ children, padding = true, className, ...rest }: CardProps) {
  return (
    <div
      className={twMerge(
        'rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900',
        padding && 'p-4',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  children?: ReactNode;
  title?: ReactNode;
}

export function CardHeader({ children, title, className, ...rest }: CardHeaderProps) {
  return (
    <div
      className={twMerge('border-b border-gray-200 px-4 py-3 dark:border-gray-700', className)}
      {...rest}
    >
      {children ?? <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{title}</h2>}
    </div>
  );
}
