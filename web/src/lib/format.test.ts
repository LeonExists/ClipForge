import { describe, expect, it } from 'vitest';
import { clampPct, formatDuration, formatRange } from './format';

describe('formatDuration', () => {
  it('sub-minute', () => {
    expect(formatDuration(36.33)).toBe('0:36');
  });
  it('minutes:seconds', () => {
    expect(formatDuration(125)).toBe('2:05');
  });
  it('hours:minutes:seconds', () => {
    expect(formatDuration(3661)).toBe('1:01:01');
  });
});

describe('formatRange', () => {
  it('shows range + duration', () => {
    expect(formatRange(21.61, 36.33)).toBe('0:21 → 0:36 (14.7s)');
  });
});

describe('clampPct', () => {
  it('clamps below 0 and above 100', () => {
    expect(clampPct(-5)).toBe(0);
    expect(clampPct(150)).toBe(100);
  });
  it('coerces NaN to 0', () => {
    expect(clampPct(NaN)).toBe(0);
  });
});
