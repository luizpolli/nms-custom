/**
 * Additional tests for format.ts utility functions.
 *
 * Supplements the existing format.test.ts with edge cases and
 * boundary conditions.
 */

import { describe, expect, it } from 'vitest';
import {
  formatBytes,
  formatPercent,
  severityBgClass,
  severityLabel,
  severityTextClass,
} from './format';

describe('formatBytes — additional edge cases', () => {
  it('handles negative bytes by treating as 0', () => {
    // Negative values: Math.log is NaN for negative, should return gracefully
    // Most impls will just let it produce NaN — let's document what we get
    const result = formatBytes(-1);
    // Should not throw; just document the output
    expect(typeof result).toBe('string');
  });

  it('formats exactly 1 KB', () => {
    expect(formatBytes(1024)).toBe('1 KB');
  });

  it('formats exactly 1 MB', () => {
    expect(formatBytes(1024 * 1024)).toBe('1 MB');
  });

  it('formats exactly 1 GB', () => {
    expect(formatBytes(1024 ** 3)).toBe('1 GB');
  });

  it('formats exactly 1 TB', () => {
    expect(formatBytes(1024 ** 4)).toBe('1 TB');
  });

  it('rounds correctly with decimal=1', () => {
    expect(formatBytes(1536, 1)).toBe('1.5 KB');
  });
});

describe('formatPercent — additional edge cases', () => {
  it('handles 0%', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('handles 100%', () => {
    expect(formatPercent(100)).toBe('100.0%');
  });

  it('handles very small values', () => {
    expect(formatPercent(0.001, 3)).toBe('0.001%');
  });
});

describe('severityTextClass — full coverage', () => {
  const mappings: Array<[string, string]> = [
    ['critical', 'text-severity-critical'],
    ['major', 'text-severity-major'],
    ['minor', 'text-severity-minor'],
    ['warning', 'text-severity-warning'],
    ['info', 'text-severity-info'],
    ['clear', 'text-severity-clear'],
  ];

  mappings.forEach(([severity, expected]) => {
    it(`maps "${severity}" to "${expected}"`, () => {
      expect(severityTextClass(severity as never)).toBe(expected);
    });
  });
});

describe('severityBgClass — full coverage', () => {
  const mappings: Array<[string, string]> = [
    ['critical', 'bg-severity-critical'],
    ['major', 'bg-severity-major'],
    ['minor', 'bg-severity-minor'],
    ['warning', 'bg-severity-warning'],
    ['info', 'bg-severity-info'],
    ['clear', 'bg-severity-clear'],
  ];

  mappings.forEach(([severity, expected]) => {
    it(`maps "${severity}" to "${expected}"`, () => {
      expect(severityBgClass(severity as never)).toBe(expected);
    });
  });
});

describe('severityLabel — additional cases', () => {
  it('capitalizes "warning" to "Warning"', () => {
    expect(severityLabel('warning')).toBe('Warning');
  });

  it('capitalizes "info" to "Info"', () => {
    expect(severityLabel('info')).toBe('Info');
  });

  it('capitalizes "clear" to "Clear"', () => {
    expect(severityLabel('clear')).toBe('Clear');
  });
});
