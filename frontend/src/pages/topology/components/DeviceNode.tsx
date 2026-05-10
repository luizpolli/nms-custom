import React from 'react';
import { Handle, Position } from 'reactflow';
import { clsx } from 'clsx';

export interface DeviceNodeData {
  label: string;
  role?: string;
  vendor?: string;
  status?: 'up' | 'down' | 'unknown';
}

const VENDOR_BORDER: Record<string, string> = {
  cisco: 'border-blue-500 dark:border-blue-400',
  juniper: 'border-green-500 dark:border-green-400',
  arista: 'border-teal-500 dark:border-teal-400',
};

const STATUS_DOT: Record<string, string> = {
  up: 'bg-green-500',
  down: 'bg-red-500',
  unknown: 'bg-gray-400',
};

export function DeviceNode({ data }: { data: DeviceNodeData }) {
  const vendor = (data.vendor ?? '').toLowerCase();
  const borderClass = VENDOR_BORDER[vendor] ?? 'border-gray-400 dark:border-gray-500';
  const dotClass = STATUS_DOT[data.status ?? 'unknown'];

  return (
    <div
      className={clsx(
        'flex items-center gap-2 rounded-lg border-2 bg-white dark:bg-gray-800 px-3 py-2 shadow-md min-w-[120px] max-w-[160px]',
        borderClass
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-gray-400" />
      <span className={clsx('h-2.5 w-2.5 rounded-full flex-shrink-0', dotClass)} />
      <div className="flex flex-col overflow-hidden">
        <span className="text-xs font-semibold text-gray-800 dark:text-gray-100 truncate">
          {data.label}
        </span>
        {data.role && (
          <span className="text-[10px] text-gray-500 dark:text-gray-400 truncate">
            {data.role}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-gray-400" />
    </div>
  );
}
