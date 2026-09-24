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
