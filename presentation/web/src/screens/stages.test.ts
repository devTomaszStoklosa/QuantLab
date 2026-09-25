import { describe, expect, it } from 'vitest';
import { captured } from '../test/api';
import { stages } from './stages';

const byKey = (detail: Parameters<typeof stages>[0]) =>
  Object.fromEntries(stages(detail).map((s) => [s.key, s.state]));

describe('pipeline stages', () => {
  it('draws the recorded gates of a concluded hypothesis', () => {
    expect(byKey(captured.momentum)).toMatchObject({
      hypothesis: 'passed',
      backtest: 'passed',
      walkforward: 'failed',
      holdout: 'skipped', // inconclusive
      conclusion: 'passed',
    });
  });

  it("draws a grid's CPCV as the in-sample gate when the definition froze it so", () => {
    const detail = structuredClone(captured.select);
    detail.run!.inSample.passed = true; // the walk-forward failed: descriptive under a CPCV gate

    const walkforward = stages(detail).find((s) => s.key === 'walkforward')!;
    expect(detail.run!.walkForward.passed).toBe(false);
    expect(walkforward).toMatchObject({ state: 'passed', meta: 'CPCV' });
  });

  it('keeps a sealed holdout locked and an unrun hypothesis pending', () => {
    expect(byKey(captured.reversal)).toMatchObject({
      hypothesis: 'passed',
      data: 'pending',
      walkforward: 'pending',
      holdout: 'locked',
      conclusion: 'pending',
    });
  });
});
