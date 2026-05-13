import { clsx } from 'clsx';

export interface AvailableReport {
  name: string;
  format: string;
  description: string;
}

interface Props {
  report: AvailableReport;
  selected: boolean;
  onClick: () => void;
}

const FORMAT_BADGE: Record<string, string> = {
  excel: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  xlsx: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  pdf: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
};

export function ReportCard({ report, selected, onClick }: Props) {
  const fmt = report.format.toLowerCase();
  const badgeClass = FORMAT_BADGE[fmt] ?? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400';

  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left rounded-lg border px-4 py-3 transition-colors',
        selected
          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 dark:border-blue-400'
          : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-900 dark:text-white">{report.name}</span>
        <span className={clsx('rounded-full px-2 py-0.5 text-xs font-medium', badgeClass)}>
          {report.format.toUpperCase()}
        </span>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">{report.description}</p>
    </button>
  );
}
