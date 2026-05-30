// ─── Widget types ─────────────────────────────────────────────────────────────

export type WidgetId =
  | 'alarm-summary'
  | 'device-status'
  | 'assurance-score'
  | 'recent-alarms'
  | 'top-cpu'
  | 'service-health'
  | 'alarm-trend'
  | 'system-health'
  | 'websocket-alarm';

/** How many grid columns / rows the widget spans */
export type WidgetColSpan = 1 | 2;
export type WidgetRowSpan = 1 | 2;

export interface WidgetSize {
  colSpan: WidgetColSpan;
  rowSpan: WidgetRowSpan;
}

/** A single widget instance placed on the dashboard */
export interface WidgetInstance {
  /** Unique instance id (allows same widget type multiple times if desired) */
  instanceId: string;
  widgetId: WidgetId;
  /** Position (index) in the grid — used for ordering */
  order: number;
  size: WidgetSize;
  minimized: boolean;
}

/** Metadata about a widget type (displayed in picker) */
export interface WidgetMeta {
  id: WidgetId;
  title: string;
  description: string;
  defaultSize: WidgetSize;
  icon: string; // emoji or text icon for picker
}

/** The full persisted layout state */
export interface DashboardLayout {
  columns: 2 | 3 | 4;
  widgets: WidgetInstance[];
}

export const WIDGET_REGISTRY: WidgetMeta[] = [
  {
    id: 'alarm-summary',
    title: 'Alarm Summary',
    description: 'Alarm counts grouped by severity (critical, major, minor, warning, info).',
    defaultSize: { colSpan: 1, rowSpan: 1 },
    icon: '🔔',
  },
  {
    id: 'device-status',
    title: 'Device Status',
    description: 'Reachable / unreachable / unknown device counts.',
    defaultSize: { colSpan: 1, rowSpan: 1 },
    icon: '🖧',
  },
  {
    id: 'assurance-score',
    title: 'Assurance Score',
    description: 'Network assurance score gauge with health state.',
    defaultSize: { colSpan: 1, rowSpan: 1 },
    icon: '🛡',
  },
  {
    id: 'recent-alarms',
    title: 'Recent Alarms',
    description: 'Scrollable list of the last 10 alarms with severity badges.',
    defaultSize: { colSpan: 1, rowSpan: 2 },
    icon: '📋',
  },
  {
    id: 'top-cpu',
    title: 'Top CPU',
    description: 'Top devices ranked by CPU utilisation.',
    defaultSize: { colSpan: 1, rowSpan: 2 },
    icon: '📊',
  },
  {
    id: 'service-health',
    title: 'Service Health',
    description: 'Summary of service assurance scores.',
    defaultSize: { colSpan: 2, rowSpan: 1 },
    icon: '🔗',
  },
  {
    id: 'alarm-trend',
    title: 'Alarm Trend',
    description: 'Alarm count trend over the last 24 hours (mini chart).',
    defaultSize: { colSpan: 2, rowSpan: 1 },
    icon: '📈',
  },
  {
    id: 'system-health',
    title: 'System Health',
    description: 'Background worker and receiver health status.',
    defaultSize: { colSpan: 1, rowSpan: 1 },
    icon: '⚙️',
  },
  {
    id: 'websocket-alarm',
    title: 'Live Alarm Feed',
    description: 'Real-time alarm feed via WebSocket.',
    defaultSize: { colSpan: 1, rowSpan: 2 },
    icon: '⚡',
  },
];

export const WIDGET_META_MAP: Record<WidgetId, WidgetMeta> = Object.fromEntries(
  WIDGET_REGISTRY.map((m) => [m.id, m]),
) as Record<WidgetId, WidgetMeta>;

export const DEFAULT_LAYOUT: DashboardLayout = {
  columns: 3,
  widgets: [
    { instanceId: 'a1', widgetId: 'alarm-summary', order: 0, size: { colSpan: 1, rowSpan: 1 }, minimized: false },
    { instanceId: 'a2', widgetId: 'device-status', order: 1, size: { colSpan: 1, rowSpan: 1 }, minimized: false },
    { instanceId: 'a3', widgetId: 'assurance-score', order: 2, size: { colSpan: 1, rowSpan: 1 }, minimized: false },
    { instanceId: 'a4', widgetId: 'recent-alarms', order: 3, size: { colSpan: 1, rowSpan: 2 }, minimized: false },
    { instanceId: 'a5', widgetId: 'top-cpu', order: 4, size: { colSpan: 1, rowSpan: 2 }, minimized: false },
    { instanceId: 'a6', widgetId: 'alarm-trend', order: 5, size: { colSpan: 2, rowSpan: 1 }, minimized: false },
    { instanceId: 'a7', widgetId: 'system-health', order: 6, size: { colSpan: 1, rowSpan: 1 }, minimized: false },
    { instanceId: 'a8', widgetId: 'websocket-alarm', order: 7, size: { colSpan: 1, rowSpan: 2 }, minimized: false },
  ],
};

export const LAYOUT_STORAGE_KEY = 'nms-dashboard-layout';
