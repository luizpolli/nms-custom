import type { WidgetId } from './types';
import { AlarmSummaryWidget } from './AlarmSummaryWidget';
import { DeviceStatusWidget } from './DeviceStatusWidget';
import { AssuranceScoreWidget } from './AssuranceScoreWidget';
import { RecentAlarmsWidget } from './RecentAlarmsWidget';
import { TopCPUWidget } from './TopCPUWidget';
import { ServiceHealthWidget } from './ServiceHealthWidget';
import { AlarmTrendWidget } from './AlarmTrendWidget';
import { SystemHealthWidget } from './SystemHealthWidget';
import { WebSocketAlarmWidget } from './WebSocketAlarmWidget';

interface WidgetRendererProps {
  widgetId: WidgetId;
}

export function WidgetRenderer({ widgetId }: WidgetRendererProps) {
  switch (widgetId) {
    case 'alarm-summary':
      return <AlarmSummaryWidget />;
    case 'device-status':
      return <DeviceStatusWidget />;
    case 'assurance-score':
      return <AssuranceScoreWidget />;
    case 'recent-alarms':
      return <RecentAlarmsWidget />;
    case 'top-cpu':
      return <TopCPUWidget />;
    case 'service-health':
      return <ServiceHealthWidget />;
    case 'alarm-trend':
      return <AlarmTrendWidget />;
    case 'system-health':
      return <SystemHealthWidget />;
    case 'websocket-alarm':
      return <WebSocketAlarmWidget />;
    default:
      return (
        <div className="p-4 text-sm text-gray-500">Unknown widget: {widgetId}</div>
      );
  }
}
