import { describe, expect, it } from 'vitest';
import { cost, day, isSynthetic, percent, pnl, probability, range, ratio, sha, significant } from './format';

describe('formatting', () => {
  it('writes ratios with 2 dp and a real minus sign', () => {
    expect(ratio(-0.6837)).toBe('−0.68');
    expect(ratio(0.9817, true)).toBe('+0.98');
  });

  it('writes a missing value as an em dash, never 0', () => {
    expect(ratio(null)).toBe('—');
    expect(percent(null)).toBe('—');
    expect(probability(null)).toBe('—');
  });

  it('writes returns as percent with 1 dp and p-values with 3 dp', () => {
    expect(percent(-0.4835)).toBe('−48.4%');
    expect(probability(0.61354)).toBe('0.614');
  });

  it('writes dates, ranges and commits as the design system asks', () => {
    expect(day('2026-09-01T09:00:00+00:00')).toBe('1 Sep 2026');
    expect(range('2020-01-01', '2022-12-31')).toBe('2020-01-01 → 2022-12-31');
    expect(sha('556db55f00')).toBe('556db55');
  });

  it('writes statistics with 4 significant digits, like the CLI', () => {
    expect(significant(1096)).toBe('1096');
    expect(significant(-5.92901)).toBe('\u22125.929');
    expect(significant(0.0011172)).toBe('0.001117');
    expect(significant(6.2e-6)).toBe('6.20e\u22126');
    expect(significant(0)).toBe('0');
    expect(significant(null)).toBe('\u2014');
  });

  it('writes costs unsigned and P&L signed, as percent of initial equity', () => {
    expect(cost(0.0038)).toBe('0.38%');
    expect(pnl(0.0123)).toBe('+1.23%');
    expect(pnl(-0.0486)).toBe('\u22124.86%');
  });

  it('recognises synthetic data among the sources of a run', () => {
    expect(isSynthetic('synthetic')).toBe(true);
    expect(isSynthetic('binance,synthetic')).toBe(true);
    expect(isSynthetic('binance')).toBe(false);
    expect(isSynthetic(null)).toBe(false);
  });
});
