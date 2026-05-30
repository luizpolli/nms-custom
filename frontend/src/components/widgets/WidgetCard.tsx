import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, GripVertical, Maximize2, Minimize2, X } from 'lucide-react';
import { Spinner } from '../ui/Spinner';
import type { WidgetSize } from './types';

interface WidgetCardProps {
  title: string;
  size: WidgetSize;
  minimized: boolean;
  loading?: boolean;
  error?: string | null;
  /** drag-and-drop handle — attach draggable props here */
  dragHandleProps?: React.HTMLAttributes<HTMLButtonElement>;
  onMinimize: () => void;
  onMaximize?: () => void;
  onRemove: () => void;
  children: ReactNode;
}

export function WidgetCard({
  title,
  minimized,
  loading = false,
  error = null,
  dragHandleProps,
  onMinimize,
  onRemove,
  children,
}: WidgetCardProps) {
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Title bar */}
      <div className="flex items-center gap-1 border-b border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800">
        {/* Drag handle */}
        <button
          type="button"
          aria-label="Drag widget"
          className="cursor-grab text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 active:cursor-grabbing"
          {...dragHandleProps}
        >
          <GripVertical className="h-4 w-4" />
        </button>

        <span className="flex-1 truncate text-sm font-semibold text-gray-700 dark:text-gray-200">
          {title}
        </span>

        <div
          className={`flex items-center gap-0.5 transition-opacity ${hovered ? 'opacity-100' : 'opacity-0'}`}
          aria-hidden={!hovered}
        >
          <button
            type="button"
            aria-label={minimized ? 'Expand widget' : 'Minimize widget'}
            onClick={onMinimize}
            className="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          >
            {minimized ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronUp className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            aria-label="Remove widget"
            onClick={onRemove}
            className="rounded p-1 text-gray-400 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-900/40 dark:hover:text-red-400"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Always visible minimize toggle */}
        <button
          type="button"
          aria-label={minimized ? 'Expand widget' : 'Minimize widget'}
          onClick={onMinimize}
          className="ml-1 rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200 md:hidden"
        >
          {minimized ? <Maximize2 className="h-3.5 w-3.5" /> : <Minimize2 className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* Body */}
      {!minimized && (
        <div className="relative flex-1 overflow-auto">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/60 dark:bg-gray-900/60">
              <Spinner />
            </div>
          )}
          {error ? (
            <div className="p-4 text-sm text-red-600 dark:text-red-400">{error}</div>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  );
}
