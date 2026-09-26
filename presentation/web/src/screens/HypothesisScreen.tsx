import { api, type HypothesisDetail } from '../api';
import { Command, Disclaimer, ErrorNotice, Loading, PageHead, SyntheticNotice } from '../components';
import { QF } from '../design-system';
import { isSynthetic, range, sha } from '../format';
import { useResource } from '../resource';
import { href } from '../route';
import {
  ContrastPanel,
  CostsPanel,
  CpcvPanel,
  DefinitionPanel,
  DiagnosticsPanel,
  EquityPanel,
  HeadlineMetrics,
  HoldoutPanel,
  MonthlyPanel,
  MultipleTestingPanel,
  NarrativePanel,
  PermutationPanel,
  PnlPanel,
  RegimesPanel,
  RunPanel,
  SealPanel,
  SelectionPanel,
  VerdictBanner,
  WalkForwardPanel,
} from './evidence';
import { stages } from './stages';
import { TradeBlotter } from './TradeBlotter';

function Evidence({ detail }: { detail: HypothesisDetail }) {
  const run = detail.run!;
  const id = detail.hypothesis.hypothesis;
  const equity = useResource(`equity:${id}`, () => api.equity(id));
  return (
    <>
      <HeadlineMetrics metrics={detail.metrics} hypothesis={detail.hypothesis} />
      {equity.state === 'ready' ? (
        <EquityPanel equity={equity.data} run={run} />
      ) : equity.state === 'failed' ? (
        <ErrorNotice error={equity.error} />
      ) : (
        <Loading />
      )}
      <NarrativePanel narrative={detail.narrative} />
      <CostsPanel metrics={detail.metrics} run={run} />
      <WalkForwardPanel windows={detail.walkForward} run={run} />
      <SelectionPanel selection={detail.selection} run={run} />
      <CpcvPanel run={run} paths={detail.cpcvPaths} choices={detail.cpcvChoices} />
      <PermutationPanel run={run} />
      <MultipleTestingPanel run={run} />
      <RegimesPanel regimes={detail.regimes} run={run} />
      <DiagnosticsPanel diagnostics={detail.diagnostics} hypothesis={detail.hypothesis} />
      <ContrastPanel run={run} />
      <MonthlyPanel detail={detail} />
      <PnlPanel groups={detail.pnlGroups} run={run} />
    </>
  );
}

export function HypothesisScreen({ id }: { id: string }) {
  const detail = useResource(`hypothesis:${id}`, () => api.hypothesis(id));

  if (detail.state === 'loading') return <Loading />;
  if (detail.state === 'failed') return <ErrorNotice error={detail.error} />;

  const h = detail.data.hypothesis;
  const run = detail.data.run;
  return (
    <>
      <PageHead
        eyebrow={<a href={href.registry}>Hypothesis registry</a>}
        title={<span className="qf-num">{h.hypothesis}</span>}
        sub={
          <>
            <QF.StatusBadge status={h.status} />
            <QF.PartitionTag partition="holdout" sealed={!h.holdout}>
              {h.holdout ? 'Holdout opened' : 'Holdout sealed'}
            </QF.PartitionTag>
            <span>{h.strategy}</span>
            <span className="qf-num">training {range(h.trainingStart, h.trainingEnd)}</span>
            <span>
              frozen at <code className="qf-code">{sha(h.frozenAtCommit)}</code>
            </span>
          </>
        }
      />
      {run && isSynthetic(run.dataSource) && <SyntheticNotice />}
      <QF.Panel>
        <QF.StageRail stages={stages(detail.data)} />
      </QF.Panel>
      <VerdictBanner {...detail.data} />
      <div className="ql-workspace">
        <div className="qf-stack">
          {run ? (
            <Evidence detail={detail.data} />
          ) : (
            <QF.Callout tone="info" title="No runs yet">
              Nothing in the results store for this hypothesis. Its training run writes it:{' '}
              <Command>{`uv run quantlab run ${h.hypothesis}`}</Command>
            </QF.Callout>
          )}
        </div>
        <div className="qf-stack">
          <DefinitionPanel hypothesis={h} />
          <SealPanel hypothesis={h} />
          <HoldoutPanel hypothesis={h} />
          {run && <RunPanel run={run} />}
        </div>
      </div>
      {run && <TradeBlotter id={h.hypothesis} instruments={detail.data.tradeInstruments} />}
      <Disclaimer />
    </>
  );
}
