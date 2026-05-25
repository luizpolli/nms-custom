interface AlarmSummary {
  critical: number;
  major: number;
  minor: number;
  warning: number;
  info: number;
  clear?: number;
}

type SeverityKey = 'critical' | 'major' | 'minor' | 'warning' | 'info' | 'clear';

interface AlarmSummaryStripProps {
  summary: AlarmSummary;
  activeSeverity?: string;
  onSelect?: (severity: SeverityKey) => void;
}

const SEVERITY_STYLES: Record<SeverityKey, string> = {
  critical: 'bg-red-600 text-white',
  major: 'bg-orange-600 text-white',
  minor: 'bg-amber-500 text-white',
  warning: 'bg-yellow-500 text-gray-900',
  info: 'bg-blue-500 text-white',
  clear: 'bg-green-600 text-white',
};

const SEVERITY_LABELS: Record<SeverityKey, string> = {
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  warning: 'Warning',
  info: 'Info',
  clear: 'Clear',
};

const ORDER: SeverityKey[] = ['critical', 'major', 'minor', 'warning', 'info', 'clear'];

export function AlarmSummaryStrip({ summary, activeSeverity, onSelect }: AlarmSummaryStripProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {ORDER.map((key) => {
        const isActive = activeSeverity === key;
        const count = summary[key] ?? 0;
        const clickable = Boolean(onSelect);
        return (
          <button
            key={key}
            type="button"
            disabled={!clickable}
            onClick={clickable ? () => onSelect!(key) : undefined}
            title={clickable ? (isActive ? `Clear ${SEVERITY_LABELS[key]} filter` : `Filter by ${SEVERITY_LABELS[key]}`) : undefined}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition ${SEVERITY_STYLES[key]} ${
              clickable ? 'cursor-pointer hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-400' : 'cursor-default'
            } ${isActive ? 'ring-2 ring-offset-1 ring-blue-400' : ''}`}
          >
            {SEVERITY_LABELS[key]}
            <span className="bg-white/20 rounded-full px-1.5">{count}</span>
          </button>
        );
      })}
    </div>
  );
}
