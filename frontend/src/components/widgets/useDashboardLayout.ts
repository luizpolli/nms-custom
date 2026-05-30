import { useCallback, useEffect, useState } from 'react';
import {
  DEFAULT_LAYOUT,
  LAYOUT_STORAGE_KEY,
} from './types';
import type { DashboardLayout, WidgetInstance, WidgetMeta } from './types';

function loadLayout(): DashboardLayout {
  try {
    const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return DEFAULT_LAYOUT;
    const parsed = JSON.parse(raw) as DashboardLayout;
    // Basic validation
    if (!Array.isArray(parsed.widgets) || ![2, 3, 4].includes(parsed.columns)) {
      return DEFAULT_LAYOUT;
    }
    return parsed;
  } catch {
    return DEFAULT_LAYOUT;
  }
}

function saveLayout(layout: DashboardLayout) {
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // Storage might be full — silently ignore
  }
}

export function useDashboardLayout() {
  const [layout, setLayoutRaw] = useState<DashboardLayout>(loadLayout);

  const setLayout = useCallback((next: DashboardLayout) => {
    setLayoutRaw(next);
    saveLayout(next);
  }, []);

  // Keep in sync with external storage changes (e.g. another tab)
  useEffect(() => {
    function onStorage(e: StorageEvent) {
      if (e.key === LAYOUT_STORAGE_KEY) {
        setLayoutRaw(loadLayout());
      }
    }
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const setColumns = useCallback(
    (cols: 2 | 3 | 4) => setLayout({ ...layout, columns: cols }),
    [layout, setLayout],
  );

  const addWidget = useCallback(
    (meta: WidgetMeta) => {
      const instanceId = `${meta.id}-${Date.now()}`;
      const maxOrder = layout.widgets.reduce((m, w) => Math.max(m, w.order), -1);
      const instance: WidgetInstance = {
        instanceId,
        widgetId: meta.id,
        order: maxOrder + 1,
        size: meta.defaultSize,
        minimized: false,
      };
      setLayout({ ...layout, widgets: [...layout.widgets, instance] });
    },
    [layout, setLayout],
  );

  const removeWidget = useCallback(
    (instanceId: string) => {
      const filtered = layout.widgets.filter((w) => w.instanceId !== instanceId);
      setLayout({ ...layout, widgets: filtered.map((w, i) => ({ ...w, order: i })) });
    },
    [layout, setLayout],
  );

  const toggleMinimize = useCallback(
    (instanceId: string) => {
      setLayout({
        ...layout,
        widgets: layout.widgets.map((w) =>
          w.instanceId === instanceId ? { ...w, minimized: !w.minimized } : w,
        ),
      });
    },
    [layout, setLayout],
  );

  const reorderWidgets = useCallback(
    (reordered: WidgetInstance[]) => setLayout({ ...layout, widgets: reordered }),
    [layout, setLayout],
  );

  const resetLayout = useCallback(() => setLayout(DEFAULT_LAYOUT), [setLayout]);

  return {
    layout,
    setColumns,
    addWidget,
    removeWidget,
    toggleMinimize,
    reorderWidgets,
    resetLayout,
  };
}
