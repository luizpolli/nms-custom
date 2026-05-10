interface AlarmSummary {
  critical: number;
  major: number;
  minor: number;
  warning: number;
  info: number;
}

interface AlarmSummaryStripProps {
  summary: AlarmSummary;
}

const SEVERITY_STYLES: Record<keyof AlarmSummary, string> = {
  critical: 'bg-red-600 text-white',
  major: 'bg-orange-600 text-white',
  minor: 'bg-amber-500 text-white',
  warning: 'bg-yellow-500 text-gray-900',
  info: 'bg-blue-500 text-white',
};

const SEVERITY_LABELS: Record<keyof AlarmSummary, string> = {
  critical: 'Critical',
  major: 'Major',
  minor: 'Minor',
  warning: 'Warning',
  info: 'Info',
};

export function AlarmSummaryStrip({ summary }: AlarmSummaryStripProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {(Object.keys(SEVERITY_STYLES) as Array<keyof AlarmSummary>).map((key) => (
        <span
          key={key}
          className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${SEVERITY_STYLES[key]}`}
        >
          {SEVERITY_LABELS[key]}
          <span className="bg-white/20 rounded-full px-1.5">{summary[key]}</span>
        </span>
      ))}
    </div>
  );
}
