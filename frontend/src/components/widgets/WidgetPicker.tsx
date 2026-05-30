import { useState } from 'react';
import { X } from 'lucide-react';
import { WIDGET_REGISTRY } from './types';
import type { WidgetMeta } from './types';

interface WidgetPickerProps {
  onAdd: (meta: WidgetMeta) => void;
  onClose: () => void;
}

export function WidgetPicker({ onAdd, onClose }: WidgetPickerProps) {
  const [search, setSearch] = useState('');

  const filtered = WIDGET_REGISTRY.filter(
    (w) =>
      w.title.toLowerCase().includes(search.toLowerCase()) ||
      w.description.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full max-w-lg rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-gray-700">
          <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">Add Widget</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close picker"
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Search */}
        <div className="px-5 pt-3">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search widgets…"
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 placeholder-gray-400 outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500"
          />
        </div>

        {/* Widget list */}
        <ul className="max-h-[60vh] overflow-y-auto px-5 py-3 space-y-2">
          {filtered.length === 0 && (
            <li className="py-6 text-center text-sm text-gray-500 dark:text-gray-400">
              No matching widgets.
            </li>
          )}
          {filtered.map((meta) => (
            <li key={meta.id}>
              <button
                type="button"
                onClick={() => { onAdd(meta); onClose(); }}
                className="flex w-full items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 text-left transition-colors hover:border-blue-400 hover:bg-blue-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-500 dark:hover:bg-blue-900/20"
              >
                <span className="text-2xl leading-none" role="img" aria-label={meta.title}>
                  {meta.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-gray-800 dark:text-gray-100">{meta.title}</div>
                  <div className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{meta.description}</div>
                  <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                    Default size: {meta.defaultSize.colSpan}×{meta.defaultSize.rowSpan}
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
