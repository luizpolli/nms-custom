import { type ReactNode, type TdHTMLAttributes, type ThHTMLAttributes } from 'react';
import { twMerge } from 'tailwind-merge';

interface ColumnDef<T = any> {
  key: string;
  header: ReactNode;
  render?: (value: unknown, row: T) => ReactNode;
}

interface TableProps<T = any> {
  children?: ReactNode;
  className?: string;
  columns?: ColumnDef<T>[];
  data?: T[];
}

export function Table<T = any>({ children, className, columns, data }: TableProps<T>) {
  const content = columns && data ? (
    <>
      <Thead>
        <Tr>
          {columns.map((col) => <Th key={col.key}>{col.header}</Th>)}
        </Tr>
      </Thead>
      <Tbody>
        {data.map((row, idx) => (
          <Tr key={String((row as any).id ?? idx)}>
            {columns.map((col) => (
              <Td key={col.key}>{col.render ? col.render((row as any)[col.key], row) : ((row as any)[col.key] as ReactNode)}</Td>
            ))}
          </Tr>
        ))}
      </Tbody>
    </>
  ) : children;
  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
      <table className={twMerge('min-w-full divide-y divide-gray-200 dark:divide-gray-700', className)}>
        {content}
      </table>
    </div>
  );
}

export function Thead({ children, className }: TableProps) {
  return (
    <thead className={twMerge('bg-gray-50 dark:bg-gray-800', className)}>
      {children}
    </thead>
  );
}

export function Tbody({ children }: TableProps) {
  return (
    <tbody className="divide-y divide-gray-200 bg-white dark:divide-gray-700 dark:bg-gray-900">
      {children}
    </tbody>
  );
}

interface ThProps extends ThHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

export function Th({ children, className, ...rest }: ThProps) {
  return (
    <th
      className={twMerge(
        'px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400',
        className,
      )}
      {...rest}
    >
      {children}
    </th>
  );
}

interface TdProps extends TdHTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

export function Td({ children, className, ...rest }: TdProps) {
  return (
    <td
      className={twMerge('px-4 py-3 text-sm text-gray-700 dark:text-gray-300', className)}
      {...rest}
    >
      {children}
    </td>
  );
}

interface TrProps {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}

export function Tr({ children, onClick, className }: TrProps) {
  return (
    <tr
      onClick={onClick}
      className={twMerge(onClick && 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800', className)}
    >
      {children}
    </tr>
  );
}
