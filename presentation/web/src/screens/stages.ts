import type { HypothesisDetail } from '../api';
import type { Stage, StageState } from '../design-system';
import { QF } from '../design-system';
import { ratio } from '../format';

const GATE: Record<string, StageState> = { true: 'passed', false: 'failed', null: 'skipped' };
const HOLDOUT: Record<string, StageState> = { passed: 'passed', rejected: 'failed', inconclusive: 'skipped' };

/**
 * The research pipeline of one hypothesis, drawn from what quantlab recorded: a stage
 * with a gate shows that gate's recorded outcome (inconclusive as skipped), a
 * descriptive stage is done once a run exists, and the holdout stays locked while sealed.
 */
export function stages({ hypothesis, run }: HypothesisDetail): Stage[] {
  const ran = (meta?: string): Pick<Stage, 'state' | 'meta'> => (run ? { state: 'passed', meta } : { state: 'pending' });
  const holdout = hypothesis.holdout;
  const concluded = ['confirmed', 'rejected', 'inconclusive'].includes(hypothesis.status);
  const byKey: Record<string, Pick<Stage, 'state' | 'meta'>> = {
    hypothesis: { state: 'passed', meta: 'frozen' },
    data: ran(hypothesis.universe),
    signal: ran(hypothesis.strategy),
    backtest: ran(run ? `Sharpe ${ratio(hypothesis.trainingSharpe)}` : undefined),
    costs: ran(run?.costSensitivity.verdict),
    walkforward: run
      ? { state: GATE[String(run.walkForward.passed)], meta: run.walkForward.passed === null ? 'inconclusive' : undefined }
      : { state: 'pending' },
    holdout: holdout ? { state: HOLDOUT[holdout.verdict], meta: holdout.verdict } : { state: 'locked', meta: 'sealed' },
    regimes: ran('descriptive'),
    attribution: ran(run ? `${run.trades.total} trades` : undefined),
    conclusion: concluded ? { state: 'passed', meta: hypothesis.status } : { state: 'pending' },
  };
  return QF.StageRail.STAGES.map(([key, label]) => ({ key, label, ...byKey[key] }));
}
