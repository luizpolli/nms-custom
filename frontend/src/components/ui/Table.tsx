import { isValidElement, type ReactNode, type TdHTMLAttributes, type ThHTMLAttributes } from 'react';
import { twMerge } from 'tailwind-merge';

type TableRow = object;

interface ColumnDef<T extends TableRow = TableRow> {
  key: string;
  header: ReactNode;
  render?: (value: unknown, row: T) => ReactNode;
}

interface TableProps<T extends TableRow = TableRow> {
  children?: ReactNode;
  className?: string;
  columns?: ColumnDef<T>[];
  data?: T[];
}

function renderValue(value: unknown): ReactNode {
  if (value == null) return null;
  if (isValidElement(value)) return value;
  if (typeof value === 'string' || typeof value === 'number') return value;
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return JSON.stringify(value);
}

function getRowValue<T extends TableRow>(row: T, key: string): unknown {
  return (row as Record<string, unknown>)[key];
}

export function Table<T extends TableRow = TableRow>({ children, className, columns, data }: TableProps<T>) {
  const content = columns && data ? (
    <>
      <Thead>
        <Tr>
          {columns.map((col) => <Th key={col.key}>{col.header}</Th>)}
        </Tr>
      </Thead>
      <Tbody>
        {data.map((row, idx) => (
          <Tr key={String(getRowValue(row, 'id') ?? idx)}>
            {columns.map((col) => {
              const value = getRowValue(row, col.key);
              return <Td key={col.key}>{col.render ? col.render(value, row) : renderValue(value)}</Td>;
            })}
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
