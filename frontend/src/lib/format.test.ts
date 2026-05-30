import { describe, expect, it } from 'vitest';
import {
  formatBytes,
  formatPercent,
  severityBgClass,
  severityLabel,
  severityTextClass,
} from './format';

describe('formatBytes', () => {
  it('returns "0 B" for zero', () => {
    expect(formatBytes(0)).toBe('0 B');
  });

  it('formats bytes below 1 KB without scaling', () => {
    expect(formatBytes(512)).toBe('512 B');
  });

  it('scales kilobytes, megabytes, and gigabytes', () => {
    expect(formatBytes(2048)).toBe('2 KB');
    expect(formatBytes(1024 * 1024 * 5)).toBe('5 MB');
    expect(formatBytes(1024 ** 3 * 3)).toBe('3 GB');
  });

  it('honors the decimals argument', () => {
    expect(formatBytes(1536, 2)).toBe('1.5 KB');
    expect(formatBytes(1536, 0)).toBe('2 KB');
  });
});

describe('formatPercent', () => {
  it('formats with default one decimal', () => {
    expect(formatPercent(42.567)).toBe('42.6%');
  });

  it('honors the decimals argument', () => {
    expect(formatPercent(99.94, 0)).toBe('100%');
    expect(formatPercent(50, 2)).toBe('50.00%');
  });
});

describe('severity helpers', () => {
  it('maps each severity to its Tailwind text class', () => {
    expect(severityTextClass('critical')).toBe('text-severity-critical');
    expect(severityTextClass('major')).toBe('text-severity-major');
    expect(severityTextClass('clear')).toBe('text-severity-clear');
  });

  it('maps each severity to its Tailwind bg class', () => {
    expect(severityBgClass('warning')).toBe('bg-severity-warning');
    expect(severityBgClass('info')).toBe('bg-severity-info');
  });

  it('returns title-cased labels', () => {
    expect(severityLabel('critical')).toBe('Critical');
    expect(severityLabel('minor')).toBe('Minor');
  });
});
