
interface Props {
  since: string;
  until: string;
  onSinceChange: (v: string) => void;
  onUntilChange: (v: string) => void;
}

export function DateRangeInput({ since, until, onSinceChange, onUntilChange }: Props) {
  const inputClass =
    'rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Desde</label>
        <input
          type="datetime-local"
          value={since}
          onChange={(e) => onSinceChange(e.target.value)}
          className={inputClass}
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Hasta</label>
        <input
          type="datetime-local"
          value={until}
          onChange={(e) => onUntilChange(e.target.value)}
          className={inputClass}
        />
      </div>
    </div>
  );
}
