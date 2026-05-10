import type { AlarmSeverity } from './types';

// ─── Date / Time ─────────────────────────────────────────────────────────────

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleDateString('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

// ─── Bytes ───────────────────────────────────────────────────────────────────

export function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(decimals))} ${sizes[i]}`;
}

// ─── Percent ─────────────────────────────────────────────────────────────────

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`;
}

// ─── Severity color (Tailwind class) ─────────────────────────────────────────

const SEVERITY_TEXT_CLASSES: Record<AlarmSeverity, string> = {
  critical: 'text-severity-critical',
  major: 'text-severity-major',
  minor: 'text-severity-minor',
  warning: 'text-severity-warning',
  info: 'text-severity-info',
  clear: 'text-severity-clear',
};

const SEVERITY_BG_CLASSES: Record<AlarmSeverity, string> = {
  critical: 'bg-severity-critical',
  major: 'bg-severity-major',
  minor: 'bg-severity-minor',
  warning: 'bg-severity-warning',
  info: 'bg-severity-info',
  clear: 'bg-severity-clear',
};

export function severityTextClass(severity: AlarmSeverity): string {
  return SEVERITY_TEXT_CLASSES[severity] ?? 'text-gray-500';
}

export function severityBgClass(severity: AlarmSeverity): string {
  return SEVERITY_BG_CLASSES[severity] ?? 'bg-gray-500';
}

export function severityLabel(severity: AlarmSeverity): string {
  const labels: Record<AlarmSeverity, string> = {
    critical: 'Crítico',
    major: 'Mayor',
    minor: 'Menor',
    warning: 'Advertencia',
    info: 'Informativo',
    clear: 'Despejado',
  };
  return labels[severity] ?? severity;
}
