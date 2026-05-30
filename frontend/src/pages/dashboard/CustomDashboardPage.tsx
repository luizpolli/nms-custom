import { useState } from 'react';
import { LayoutGrid, Plus, RefreshCcw } from 'lucide-react';
import { WidgetGrid } from '../../components/widgets/WidgetGrid';
import { WidgetCard } from '../../components/widgets/WidgetCard';
import { WidgetPicker } from '../../components/widgets/WidgetPicker';
import { WidgetRenderer } from '../../components/widgets/WidgetRenderer';
import { useDashboardLayout } from '../../components/widgets/useDashboardLayout';
import { WIDGET_META_MAP } from '../../components/widgets/types';
import { PageHeader } from '../../components/ui/PageHeader';
import type { WidgetInstance } from '../../components/widgets/types';

const COLUMN_OPTIONS: { value: 2 | 3 | 4; label: string }[] = [
  { value: 2, label: '2 col' },
  { value: 3, label: '3 col' },
  { value: 4, label: '4 col' },
];

export function CustomDashboardPage() {
  const {
    layout,
    setColumns,
    addWidget,
    removeWidget,
    toggleMinimize,
    reorderWidgets,
    resetLayout,
  } = useDashboardLayout();

  const [pickerOpen, setPickerOpen] = useState(false);

  const renderWidget = (instance: WidgetInstance) => {
    const meta = WIDGET_META_MAP[instance.widgetId];
    return (
      <WidgetCard
        key={instance.instanceId}
        title={meta?.title ?? instance.widgetId}
        size={instance.size}
        minimized={instance.minimized}
        onMinimize={() => toggleMinimize(instance.instanceId)}
        onRemove={() => removeWidget(instance.instanceId)}
      >
        <WidgetRenderer widgetId={instance.widgetId} />
      </WidgetCard>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Custom Dashboard"
        subtitle="Drag widgets to rearrange · click × to remove · use Add Widget to expand"
      />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Column selector */}
        <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-1 dark:border-gray-700 dark:bg-gray-900">
          <LayoutGrid className="ml-1 h-4 w-4 text-gray-400" />
          {COLUMN_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setColumns(opt.value)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                layout.columns === opt.value
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Spacer */}
        <span className="flex-1" />

        {/* Reset */}
        <button
          type="button"
          onClick={resetLayout}
          className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
        >
          <RefreshCcw className="h-4 w-4" />
          Reset to default
        </button>

        {/* Add widget */}
        <button
          type="button"
          onClick={() => setPickerOpen(true)}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          Add Widget
        </button>
      </div>

      {/* Empty state */}
      {layout.widgets.length === 0 && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-gray-300 py-20 text-center dark:border-gray-700">
          <LayoutGrid className="h-10 w-10 text-gray-300 dark:text-gray-600" />
          <div>
            <p className="font-medium text-gray-600 dark:text-gray-300">Your dashboard is empty</p>
            <p className="mt-1 text-sm text-gray-400 dark:text-gray-500">
              Click <strong>Add Widget</strong> to get started.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setPickerOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            Add Widget
          </button>
        </div>
      )}

      {/* Widget grid */}
      {layout.widgets.length > 0 && (
        <WidgetGrid
          columns={layout.columns}
          widgets={layout.widgets}
          onReorder={reorderWidgets}
          renderWidget={renderWidget}
        />
      )}

      {/* Widget picker modal */}
      {pickerOpen && (
        <WidgetPicker
          onAdd={addWidget}
          onClose={() => setPickerOpen(false)}
        />
      )}
    </div>
  );
}

export default CustomDashboardPage;
