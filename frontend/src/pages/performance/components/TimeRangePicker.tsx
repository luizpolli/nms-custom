import { useState } from 'react';
import clsx from 'clsx';

export interface TimeRange {
  since: string;
  until: string;
}

type Preset = '1h' | '6h' | '24h' | '7d' | 'custom';

interface TimeRangePickerProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

const PRESETS: { label: string; key: Preset; hours: number }[] = [
  { label: '1h', key: '1h', hours: 1 },
  { label: '6h', key: '6h', hours: 6 },
  { label: '24h', key: '24h', hours: 24 },
  { label: '7d', key: '7d', hours: 168 },
];

function hoursAgo(hours: number): TimeRange {
  const until = new Date();
  const since = new Date(until.getTime() - hours * 3600_000);
  return { since: since.toISOString(), until: until.toISOString() };
}

export function TimeRangePicker({ onChange }: TimeRangePickerProps) {
  const [active, setActive] = useState<Preset>('1h');
  const [customSince, setCustomSince] = useState('');
  const [customUntil, setCustomUntil] = useState('');

  function selectPreset(p: typeof PRESETS[0]) {
    setActive(p.key);
    onChange(hoursAgo(p.hours));
  }

  function applyCustom() {
    if (customSince && customUntil) {
      onChange({ since: new Date(customSince).toISOString(), until: new Date(customUntil).toISOString() });
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((p) => (
        <button
          key={p.key}
          type="button"
          onClick={() => selectPreset(p)}
          className={clsx(
            'px-3 py-1 rounded-full text-xs font-medium border transition-colors',
            active === p.key
              ? 'bg-blue-600 text-white border-blue-600'
              : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-500',
          )}
        >
          {p.label}
        </button>
      ))}
      <button
        type="button"
        onClick={() => setActive('custom')}
        className={clsx(
          'px-3 py-1 rounded-full text-xs font-medium border transition-colors',
          active === 'custom'
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-600 hover:border-blue-500',
        )}
      >
        Personalizado
      </button>
      {active === 'custom' && (
        <div className="flex items-center gap-2 mt-1 w-full">
          <input
            type="datetime-local"
            value={customSince}
            onChange={(e) => setCustomSince(e.target.value)}
            className="text-xs border rounded px-2 py-1 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
          />
          <span className="text-xs text-gray-500">—</span>
          <input
            type="datetime-local"
            value={customUntil}
            onChange={(e) => setCustomUntil(e.target.value)}
            className="text-xs border rounded px-2 py-1 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
          />
          <button
            type="button"
            onClick={applyCustom}
            className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
          >
            Aplicar
          </button>
        </div>
      )}
    </div>
  );
}
