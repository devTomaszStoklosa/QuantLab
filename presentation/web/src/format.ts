// Display formatting only (design system: "code computes, the UI formats").
import { QF } from './design-system';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Ratios (Sharpe, Sortino, Calmar): 2 dp, U+2212 minus, "—" for null. */
export const ratio = (value: number | null, sign = false) => QF.format.num(value, 2, sign);

/** Returns and drawdowns: 1 dp percent. */
export const percent = (value: number | null, sign = false) => QF.format.pct(value, 1, sign);

/** p-values and probabilities: 3 dp. */
export const probability = (value: number | null) => QF.format.num(value, 3);

/** An ISO date or timestamp as the UI writes it: 14 Aug 2026. */
export function day(iso: string): string {
  const [year, month, dayOfMonth] = iso.slice(0, 10).split('-').map(Number);
  return `${dayOfMonth} ${MONTHS[month - 1]} ${year}`;
}

/** A range as it is written in parameters and code: 2019-01-01 → 2023-12-31. */
export const range = (start: string, end: string) => `${start} → ${end}`;

export const sha = (commit: string) => commit.slice(0, 7);

export const isSynthetic = (dataSource: string | null | undefined) =>
  dataSource?.split(',').includes('synthetic') ?? false;
