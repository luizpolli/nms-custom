import { useCallback, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import type { WidgetInstance } from './types';

interface WidgetGridProps {
  columns: 2 | 3 | 4;
  widgets: WidgetInstance[];
  onReorder: (reordered: WidgetInstance[]) => void;
  renderWidget: (instance: WidgetInstance) => React.ReactNode;
}

const COLUMN_CLASS: Record<2 | 3 | 4, string> = {
  2: 'grid-cols-1 sm:grid-cols-2',
  3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
  4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
};

export function WidgetGrid({ columns, widgets, onReorder, renderWidget }: WidgetGridProps) {
  const dragSourceId = useRef<string | null>(null);
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  const sorted = [...widgets].sort((a, b) => a.order - b.order);

  const handleDragStart = useCallback((e: DragEvent<HTMLDivElement>, instanceId: string) => {
    dragSourceId.current = instanceId;
    e.dataTransfer.effectAllowed = 'move';
    // Required for Firefox
    e.dataTransfer.setData('text/plain', instanceId);
  }, []);

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>, instanceId: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (instanceId !== dragSourceId.current) {
      setDragOverId(instanceId);
    }
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverId(null);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>, targetId: string) => {
      e.preventDefault();
      setDragOverId(null);

      const sourceId = dragSourceId.current;
      if (!sourceId || sourceId === targetId) return;

      const sourceIdx = sorted.findIndex((w) => w.instanceId === sourceId);
      const targetIdx = sorted.findIndex((w) => w.instanceId === targetId);
      if (sourceIdx === -1 || targetIdx === -1) return;

      // Swap orders
      const updated = sorted.map((w, i) => {
        if (i === sourceIdx) return { ...w, order: sorted[targetIdx].order };
        if (i === targetIdx) return { ...w, order: sorted[sourceIdx].order };
        return w;
      });
      // Normalise orders to be 0-based sequential after swap
      const sorted2 = [...updated].sort((a, b) => a.order - b.order);
      onReorder(sorted2.map((w, i) => ({ ...w, order: i })));
    },
    [sorted, onReorder],
  );

  const handleDragEnd = useCallback(() => {
    dragSourceId.current = null;
    setDragOverId(null);
  }, []);

  return (
    <div className={`grid gap-4 ${COLUMN_CLASS[columns]}`}>
      {sorted.map((instance) => {
        const colSpanClass =
          instance.size.colSpan === 2
            ? columns >= 2
              ? 'sm:col-span-2'
              : ''
            : '';
        const rowSpanClass = instance.size.rowSpan === 2 ? 'row-span-2' : '';
        const isDragOver = dragOverId === instance.instanceId;

        return (
          <div
            key={instance.instanceId}
            className={`${colSpanClass} ${rowSpanClass} ${isDragOver ? 'ring-2 ring-blue-400 ring-offset-1 rounded-lg' : ''} transition-shadow`}
            draggable
            onDragStart={(e) => handleDragStart(e, instance.instanceId)}
            onDragOver={(e) => handleDragOver(e, instance.instanceId)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, instance.instanceId)}
            onDragEnd={handleDragEnd}
          >
            {renderWidget(instance)}
          </div>
        );
      })}
    </div>
  );
}
