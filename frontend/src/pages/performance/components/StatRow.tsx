import { StatCard } from '../../../components/ui';

export interface StatRowItem {
  label: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'neutral';
}

interface StatRowProps {
  items: StatRowItem[];
}

export function StatRow({ items }: StatRowProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={`${item.value}${item.unit ?? ''}`}
          trend={item.trend}
        />
      ))}
    </div>
  );
}
