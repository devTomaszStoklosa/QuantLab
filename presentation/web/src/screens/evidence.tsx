// Panels of the hypothesis screen: each shows numbers the API returned, formatted only.
import type { ReactNode } from 'react';
import type {
  CostModelMetrics,
  CpcvChoice,
  CpcvPath,
  Diagnostic,
  EquityPoint,
  HypothesisDetail,
  HypothesisSummary,
  NarrativeParagraph,
  PnlGroup,
  RegimeMetrics,
  InSampleValidation,
  RunSummary,
  SelectionCell,
  SignificanceTest,
  WalkForwardWindow,
} from '../api';
import { QF, type Column } from '../design-system';
import { cost, day, percent, pnl, probability, range, ratio, sha, significant } from '../format';

const OUTCOME = { true: 'passed', false: 'failed', null: 'inconclusive' } as const;
const outcome = (passed: boolean | null) => OUTCOME[String(passed) as keyof typeof OUTCOME];

// How each significance test reads: the day shuffle asks about timing, random
// portfolios from the same cross-section about selection.
const TEST_WORDING: Record<SignificanceTest, { title: string; draws: string; nullMean: string; beats: string }> = {
  day_shuffle: {
    title: 'Permutation test',
    draws: 'shuffles of returns against the positions held',
    nullMean: 'Shuffled mean',
    beats: 'Beats shuffles',
  },
  random_portfolio: {
    title: 'Random-portfolio test',
    draws: "random portfolios from each decision's cross-section",
    nullMean: 'Random mean',
    beats: 'Beats random portfolios',
  },
};

// The frozen in-sample gate, as the verdict names it.
export const GATE_NAMES: Record<InSampleValidation, string> = { walk_forward: 'walk-forward', cpcv: 'CPCV' };

const lossTone = (value: number | null) => (value == null ? 'dim' : value < 0 ? 'loss' : null);

const badge = (passed: boolean | null) => (
  <QF.StatusBadge status={passed === true ? 'confirmed' : passed === false ? 'rejected' : 'inconclusive'}>{outcome(passed)}</QF.StatusBadge>
);

function Descriptive() {
  return <span className="qf-muted">Descriptive only: not part of any pass rule or of the verdict.</span>;
}

function KeyValues({ rows }: { rows: Array<[ReactNode, ReactNode]> }) {
  return (
    <dl className="qf-kv">
      {rows.map(([label, value], i) => (
        <div key={i} style={{ display: 'contents' }}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The verdict once the holdout is open; before that, the plain statement that there is none. */
export function VerdictBanner({ hypothesis, run }: HypothesisDetail) {
  const holdout = hypothesis.holdout;
  if (!holdout) {
    return (
      <QF.Callout tone="frozen" title="No verdict until the frozen holdout is opened">
        The holdout {range(hypothesis.holdoutStart, hypothesis.holdoutEnd)} has not been read by any run. It is
        opened once, from the command line, after the training results are reviewed:{' '}
        <code className="qf-code">uv run quantlab open-holdout {hypothesis.hypothesis}</code>. Its result is final
        and is recorded whatever it is.
      </QF.Callout>
    );
  }
  const gate = GATE_NAMES[hypothesis.inSampleValidation];
  const walkForward = run ? `${gate} ${outcome(run.inSample.passed)}` : `no stored ${gate}`;
  return (
    <QF.Verdict
      verdict={hypothesis.status === 'confirmed' || hypothesis.status === 'rejected' ? hypothesis.status : 'inconclusive'}
      meta={
        <>
          Holdout {range(hypothesis.holdoutStart, hypothesis.holdoutEnd)} opened {day(holdout.openedAt)} at{' '}
          <code className="qf-code">{sha(holdout.openedAtCommit)}</code> · {holdout.costModel}
        </>
      }
    >
      {walkForward[0].toUpperCase() + walkForward.slice(1)}; holdout {holdout.verdict} (net Sharpe{' '}
      {ratio(holdout.sharpe)}, p = {probability(holdout.pValue)}). {hypothesis.criterion}
    </QF.Verdict>
  );
}

export function HeadlineMetrics({ metrics, hypothesis }: { metrics: CostModelMetrics[]; hypothesis: HypothesisSummary }) {
  const primary = metrics.find((m) => m.primary);
  const holdout = hypothesis.holdout;
  return (
    <QF.MetricStrip
      columns={4}
      items={[
        { label: 'Sharpe, net', partition: 'is', value: ratio(primary?.sharpe ?? null), hint: 'training' },
        { label: 'CAGR, net', partition: 'is', value: percent(primary?.cagr ?? null), hint: 'training' },
        { label: 'Max drawdown', partition: 'is', value: percent(primary?.maxDrawdown ?? null), hint: 'training' },
        holdout
          ? { label: 'Sharpe, net', partition: 'holdout', value: ratio(holdout.sharpe), hint: `p = ${probability(holdout.pValue)}` }
          : { label: 'Sharpe, net', partition: 'holdout', sealed: true, value: '—', hint: 'sealed until opened' },
      ]}
    />
  );
}

export function EquityPanel({ equity, run }: { equity: EquityPoint[]; run: RunSummary }) {
  const ticks = equity
    .map((point, i) => ({ i, year: point.ts.slice(0, 4) }))
    .filter((point, i, all) => i === 0 || point.year !== all[i - 1].year)
    .map(({ i, year }) => ({ i, label: year }));
  return (
    <QF.Panel title="Equity, net of costs" subtitle={`Training ${range(run.start, run.end)} · ${run.costModel} · started at 1`}>
      {equity.length > 1 ? (
        <QF.EquityChart
          series={equity.map((p) => p.equity)}
          drawdown={equity.map((p) => p.drawdown)}
          xTicks={ticks}
          partitions={[{ kind: 'is', from: 0, to: equity.length - 1, label: 'TRAINING' }]}
          yFormat={(v) => QF.format.num(v, 2)}
          ariaLabel={`Equity curve of the training run, ${run.costModel}`}
        />
      ) : (
        <p className="qf-muted">No equity points.</p>
      )}
    </QF.Panel>
  );
}

const METRIC_COLUMNS: Column<CostModelMetrics & { id: string }>[] = [
  { key: 'costModel', label: 'Cost model', render: (v: string) => <code className="qf-code">{v}</code> },
  { key: 'cagr', label: 'CAGR', numeric: true, format: (v) => percent(v), tone: lossTone },
  { key: 'sharpe', label: 'Sharpe', numeric: true, format: (v) => ratio(v), tone: lossTone },
  { key: 'sortino', label: 'Sortino', numeric: true, format: (v) => ratio(v), tone: lossTone },
  { key: 'calmar', label: 'Calmar', numeric: true, format: (v) => ratio(v), tone: lossTone },
  { key: 'maxDrawdown', label: 'Max drawdown', numeric: true, format: (v) => percent(v) },
  { key: 'turnover', label: 'Turnover', numeric: true, format: (v: number) => `${QF.format.num(v, 1)}×/yr` },
];

export function CostsPanel({ metrics, run }: { metrics: CostModelMetrics[]; run: RunSummary }) {
  const sensitivity = run.costSensitivity;
  const primary = metrics.find((m) => m.primary)?.costModel;
  return (
    <QF.Panel
      title="Costs"
      icon="costs"
      subtitle="The same run under each cost model"
      flush
      footer={
        <>
          Cost sensitivity: <b>{sensitivity.verdict}</b> (Sharpe difference {ratio(sensitivity.sharpeDifference)}
          {sensitivity.cagrSignFlip ? ', CAGR changes sign' : ''})
        </>
      }
    >
      <QF.DataTable rows={metrics.map((m) => ({ ...m, id: m.costModel }))} selected={primary} columns={METRIC_COLUMNS} />
    </QF.Panel>
  );
}

const WINDOW_COLUMNS: Column<WalkForwardWindow & { id: string }>[] = [
  {
    key: 'start',
    label: 'Window',
    render: (_: string, w) =>
      w.aggregate ? <b>Aggregate</b> : <span className="qf-num ql-nowrap">{range(w.start, w.end)}{w.partial ? ' *' : ''}</span>,
  },
  { key: 'cagr', label: 'CAGR', numeric: true, format: (v) => percent(v), tone: lossTone },
  { key: 'sharpe', label: 'Sharpe', numeric: true, format: (v) => ratio(v), tone: lossTone },
  { key: 'maxDrawdown', label: 'Max drawdown', numeric: true, format: (v) => percent(v) },
];

export function WalkForwardPanel({ windows, run }: { windows: WalkForwardWindow[]; run: RunSummary }) {
  const wf = run.walkForward;
  const gate = run.inSample.validation;
  return (
    <QF.Panel
      title="Walk-forward"
      icon="repeat"
      subtitle="Calendar-year windows from the first position; * partial year"
      tag={badge(wf.passed)}
      flush
      footer={
        <>
          {wf.positiveWindows} of {wf.windowsWithSharpe} windows with Sharpe &gt; 0. Rule: {wf.rule}
          {gate !== 'walk_forward' && (
            <>
              {' '}
              <span className="qf-muted">
                Descriptive only: this hypothesis's frozen in-sample gate is {GATE_NAMES[gate]}.
              </span>
            </>
          )}
        </>
      }
    >
      <QF.DataTable rows={windows.map((w, i) => ({ ...w, id: String(i) }))} columns={WINDOW_COLUMNS} />
    </QF.Panel>
  );
}

type SelectionRow = { id: string; year: number; days: number; chosen: string | null; sharpes: Record<string, number | null> };

/** Each year's choice from the grid, with every value's Sharpe on the history before it (q8, REQ-841). */
export function SelectionPanel({ selection, run }: { selection: SelectionCell[]; run: RunSummary }) {
  const grid = run.grid;
  if (!grid) return null;
  const values = [...new Set(selection.map((cell) => cell.value))];
  const rows: SelectionRow[] = [...new Set(selection.map((cell) => cell.year))].map((year) => {
    const cells = selection.filter((cell) => cell.year === year);
    return {
      id: String(year),
      year,
      days: cells[0].days,
      chosen: cells.find((cell) => cell.chosen)?.value ?? null,
      sharpes: Object.fromEntries(cells.map((cell) => [cell.value, cell.sharpe])),
    };
  });
  const columns: Column<SelectionRow>[] = [
    { key: 'year', label: 'Year', render: (year: number) => <span className="qf-num">{year}</span> },
    ...values.map(
      (value): Column<SelectionRow> => ({
        key: `sharpe:${value}`,
        label: value,
        numeric: true,
        render: (_: unknown, row) => (row.chosen === value ? <b>{ratio(row.sharpes[value])}</b> : ratio(row.sharpes[value])),
        tone: (_: unknown, row) => lossTone(row.sharpes[value]),
      }),
    ),
    {
      key: 'chosen',
      label: 'Chosen',
      render: (chosen: string | null, row) =>
        chosen ?? <span className="qf-muted">none ({row.days} days of history)</span>,
    },
  ];
  const pbo = grid.pbo;
  return (
    <QF.Panel
      title="Parameter selection"
      icon="filter"
      subtitle={`Grid ${values.join(', ')} · each year's value has the best net Sharpe on the history before 1 January · Sharpe annualized`}
      flush
      footer={
        <>
          {pbo
            ? `PBO of choosing from the grid (CSCV, ${pbo.blocks} blocks, ${pbo.splits.toLocaleString('en-US')} splits, ${range(grid.start, grid.end)}): ${ratio(pbo.value)}. `
            : 'PBO of choosing from the grid: n/a (too few days). '}
          <Descriptive />
        </>
      }
    >
      <QF.DataTable rows={rows} columns={columns} />
    </QF.Panel>
  );
}

/** The CPCV of the choosing procedure: many out-of-sample paths from one history (q8, REQ-841). */
export function CpcvPanel({ run, paths, choices }: { run: RunSummary; paths: CpcvPath[]; choices: CpcvChoice[] }) {
  const grid = run.grid;
  if (!grid) return null;
  const c = grid.cpcv;
  const gate = run.inSample.validation === 'cpcv';
  return (
    <QF.Panel
      title="CPCV of the selection"
      icon="validate"
      subtitle={`${c.groups} groups, ${c.testGroups} for testing · purge ${c.purge}, embargo ${c.embargo} days · ${c.splits} splits, ${c.paths} paths · ${range(grid.start, grid.end)}`}
      tag={gate ? badge(run.inSample.passed) : undefined}
      footer={
        <>
          {gate ? <>In-sample gate (frozen). Rule: {c.rule}. </> : <Descriptive />} Switches between a path's segments
          are not costed.
        </>
      }
    >
      <div className="qf-stack">
        <QF.MetricStrip
          columns={4}
          items={[
            { label: 'Median path Sharpe', partition: 'is', value: ratio(c.medianSharpe) },
            { label: 'Mean path Sharpe', value: ratio(c.meanSharpe) },
            { label: 'Lowest / highest', value: `${ratio(c.minSharpe)} / ${ratio(c.maxSharpe)}` },
            { label: 'Paths with Sharpe > 0', value: percent(c.positiveShare) },
          ]}
        />
        <KeyValues
          rows={[
            ['Path Sharpes', <span className="qf-num">{paths.map((path) => ratio(path.sharpe)).join(', ')}</span>],
            [
              'Chosen in the splits',
              <span className="qf-num">{choices.map((choice) => `${choice.value} ${percent(choice.share)}`).join(', ')}</span>,
            ],
          ]}
        />
      </div>
    </QF.Panel>
  );
}

export function PermutationPanel({ run }: { run: RunSummary }) {
  const p = run.permutation;
  const wording = TEST_WORDING[p.test];
  return (
    <QF.Panel
      title={wording.title}
      icon="shuffle"
      subtitle={`${p.count.toLocaleString('en-US')} ${wording.draws} · seed ${p.seed} · ${p.statistic}`}
      footer={
        p.reason
          ? `Inconclusive: ${p.reason}`
          : `p = ${probability(p.pValue)}: ${p.passed ? `significant at ${p.alpha}` : `not significant at ${p.alpha}`}`
      }
    >
      {p.lowConfidence && (
        <QF.Callout tone="warning" title="Low confidence">
          Only {p.activeDays} days with a position.
        </QF.Callout>
      )}
      <QF.MetricStrip
        columns={4}
        items={[
          { label: 'Gross Sharpe', partition: 'is', value: ratio(p.actual) },
          { label: wording.nullMean, value: ratio(p.nullMean), hint: `sd ${ratio(p.nullStd)}` },
          { label: wording.beats, value: percent(p.percentile) },
          { label: 'p-value', value: probability(p.pValue) },
        ]}
      />
    </QF.Panel>
  );
}

const REGIME_COLUMNS: Column<RegimeMetrics & { id: string }>[] = [
  { key: 'regime', label: 'Regime' },
  { key: 'days', label: 'Days', numeric: true },
  { key: 'share', label: 'Share', numeric: true, format: (v: number) => percent(v) },
  { key: 'cagr', label: 'CAGR', numeric: true, format: (v) => percent(v), tone: lossTone },
  { key: 'sharpe', label: 'Sharpe', numeric: true, format: (v) => ratio(v), tone: lossTone },
  { key: 'sortino', label: 'Sortino', numeric: true, format: (v) => ratio(v), tone: lossTone },
];

export function RegimesPanel({ regimes, run }: { regimes: RegimeMetrics[]; run: RunSummary }) {
  return (
    <QF.Panel title="Regimes" icon="regime" subtitle={run.regimeMethod} flush footer={<Descriptive />}>
      <QF.DataTable rows={regimes.map((r) => ({ ...r, id: r.regime }))} columns={REGIME_COLUMNS} />
    </QF.Panel>
  );
}

export function MultipleTestingPanel({ run }: { run: RunSummary }) {
  const m = run.multipleTesting;
  // A grid's values each count as a configuration (q8, REQ-820).
  const grids = m.configurations !== m.trials.length;
  const configurations = grids ? ` · ${m.configurations} parameter configurations among them` : '';
  return (
    <QF.Panel
      title="Multiple testing"
      icon="validate"
      subtitle={`${m.trials.length} trials on this universe and training period: ${m.trials.join(', ')}${configurations} · ${m.returnsCount} daily returns`}
      footer={<Descriptive />}
    >
      <QF.MetricStrip
        columns={4}
        items={[
          { label: 'Sharpe, net', partition: 'is', value: ratio(m.sharpeAnnualized), hint: 'from the first position' },
          { label: 'PSR (Sharpe > 0)', value: ratio(m.psr) },
          {
            label: `Best of ${m.configurations} no-edge ${grids ? 'configurations' : 'trials'}`,
            value: ratio(m.dsrThreshold),
            hint: 'expected Sharpe',
          },
          { label: 'Deflated Sharpe', value: ratio(m.dsr) },
        ]}
      />
    </QF.Panel>
  );
}

export function DiagnosticsPanel({ diagnostics, hypothesis }: { diagnostics: Diagnostic[]; hypothesis: HypothesisSummary }) {
  const titles = [...new Set(diagnostics.map((d) => d.title))];
  return (
    <>
      {titles.map((title) => (
        <QF.Panel key={title} title={title} subtitle={`Training ${range(hypothesis.trainingStart, hypothesis.trainingEnd)}`} footer={<Descriptive />}>
          <KeyValues
            rows={diagnostics
              .filter((d) => d.title === title)
              .map((d) => [d.label, <span className="qf-num">{significant(d.value)}</span>])}
          />
        </QF.Panel>
      ))}
    </>
  );
}

export function NarrativePanel({ narrative }: { narrative: NarrativeParagraph[] }) {
  if (narrative.length === 0) return null;
  const sections = [...new Set(narrative.map((p) => p.section))];
  return (
    <QF.Panel
      title="Narrative"
      icon="report"
      subtitle="The stored numbers in words, in Polish like the lab's reports"
      footer={<span className="qf-muted">Composed by quantlab from templates over the computed numbers; no advice.</span>}
    >
      <div className="qf-stack" lang="pl">
        {sections.map((section) => (
          <div key={section}>
            <div className="qf-eyebrow" style={{ marginBottom: 8 }}>
              {section}
            </div>
            {narrative
              .filter((p) => p.section === section)
              .map((p, i) => (
                <p key={i} style={{ margin: '0 0 8px' }}>
                  {p.text}
                </p>
              ))}
          </div>
        ))}
      </div>
    </QF.Panel>
  );
}

export function ContrastPanel({ run }: { run: RunSummary }) {
  if (!run.contrast) return null;
  return (
    <QF.Panel title="Contrast" icon="signal" subtitle={`With ${run.contrast.hypothesis} · ${run.contrast.costModel}`} footer={<Descriptive />}>
      <QF.MetricStrip
        columns={1}
        items={[{ label: 'Correlation of daily net returns, days both held a position', value: ratio(run.contrast.correlation, true) }]}
      />
    </QF.Panel>
  );
}

export function MonthlyPanel({ detail }: { detail: HypothesisDetail }) {
  const years = detail.yearly.map((y) => ({
    year: y.year,
    total: y.netReturn,
    months: Array.from({ length: 12 }, (_, i) => detail.monthly.find((m) => m.year === y.year && m.month === i + 1)?.netReturn ?? null),
  }));
  return (
    <QF.Panel title="Monthly net returns" icon="report" subtitle="Percent, net of costs; the year column is the year's return">
      <QF.MonthlyHeatmap years={years} />
    </QF.Panel>
  );
}

const GROUP_COLUMNS: Column<PnlGroup & { id: string }>[] = [
  { key: 'key', label: 'Group' },
  { key: 'trades', label: 'Trades', numeric: true },
  { key: 'winRate', label: 'Win rate', numeric: true, format: (v: number) => percent(v) },
  { key: 'totalNetPnl', label: 'Total', numeric: true, format: (v: number) => pnl(v), tone: lossTone },
  { key: 'meanNetPnl', label: 'Mean', numeric: true, format: (v: number) => pnl(v), tone: lossTone },
  { key: 'medianNetPnl', label: 'Median', numeric: true, format: (v: number) => pnl(v), tone: lossTone },
  { key: 'worstNetPnl', label: 'Worst', numeric: true, format: (v: number) => pnl(v), tone: lossTone },
  { key: 'bestNetPnl', label: 'Best', numeric: true, format: (v: number) => pnl(v), tone: lossTone },
  { key: 'costs', label: 'Costs', numeric: true, format: (v: number) => cost(v) },
];

export function PnlPanel({ groups, run }: { groups: PnlGroup[]; run: RunSummary }) {
  const dimensions: Array<[PnlGroup['dimension'], string]> = [
    ['regime', 'By regime at entry'],
    ['holding_period', 'By holding period'],
    ['asset_class', 'By asset class'],
    ['instrument', 'By instrument'],
  ];
  return (
    <QF.Panel
      title="Where the P&L came from"
      icon="attribution"
      subtitle={`${run.trades.total} trades (${run.trades.openAtEnd} open at the end) · P&L as percent of initial equity`}
      footer={<Descriptive />}
    >
      <div className="qf-stack">
        {dimensions.map(([dimension, title]) => {
          const rows = groups.filter((g) => g.dimension === dimension);
          return rows.length === 0 ? null : (
            <div key={dimension}>
              <div className="qf-eyebrow" style={{ marginBottom: 8 }}>
                {title}
              </div>
              <QF.DataTable dense rows={rows.map((g) => ({ ...g, id: g.key }))} columns={GROUP_COLUMNS} />
            </div>
          );
        })}
      </div>
    </QF.Panel>
  );
}

export function DefinitionPanel({ hypothesis }: { hypothesis: HypothesisSummary }) {
  const { strategy, universe, cost_model: _cost, ...parameters } = hypothesis.parameters as Record<string, unknown>;
  return (
    <QF.Panel title="Frozen definition" icon="lock" subtitle={`config/holdout/${hypothesis.hypothesis}.yaml`}>
      <KeyValues
        rows={[
          ['Strategy', <code className="qf-code">{String(strategy)}</code>],
          ...Object.entries(parameters).map(([name, value]): [ReactNode, ReactNode] => [
            name,
            <span className="qf-num">{value === null ? '—' : Array.isArray(value) ? value.join(', ') : String(value)}</span>,
          ]),
          ['Universe', String(universe)],
          ['Cost model', <code className="qf-code">{hypothesis.costModel}</code>],
          ['In-sample gate', GATE_NAMES[hypothesis.inSampleValidation]],
          ['Training', <span className="qf-num">{range(hypothesis.trainingStart, hypothesis.trainingEnd)}</span>],
          ['Registered', day(hypothesis.registeredAt)],
          ['Trials on its data', <span className="qf-num">{hypothesis.trialsOnSameData}</span>],
        ]}
      />
    </QF.Panel>
  );
}

export function SealPanel({ hypothesis }: { hypothesis: HypothesisSummary }) {
  const holdout = hypothesis.holdout;
  return (
    <QF.HoldoutSeal
      state={holdout ? 'unsealed' : 'sealed'}
      range={range(hypothesis.holdoutStart, hypothesis.holdoutEnd)}
      sha={sha(hypothesis.frozenAtCommit)}
      frozenAt={day(hypothesis.registeredAt)}
      criterion={hypothesis.criterion}
      openedAt={holdout ? `${day(holdout.openedAt)} at ${sha(holdout.openedAtCommit)}` : undefined}
    />
  );
}

export function HoldoutPanel({ hypothesis }: { hypothesis: HypothesisSummary }) {
  const holdout = hypothesis.holdout;
  if (!holdout) return null;
  return (
    <QF.Panel title="Holdout result" icon="unlock" subtitle={`${range(hypothesis.holdoutStart, hypothesis.holdoutEnd)} · ${holdout.costModel}`}>
      <KeyValues
        rows={[
          ['Verdict', <b>{holdout.verdict}</b>],
          ['Sharpe, net', <span className="qf-num">{ratio(holdout.sharpe)}</span>],
          ['CAGR', <span className="qf-num">{percent(holdout.cagr)}</span>],
          ['Sortino', <span className="qf-num">{ratio(holdout.sortino)}</span>],
          ['Calmar', <span className="qf-num">{ratio(holdout.calmar)}</span>],
          ['Max drawdown', <span className="qf-num">{percent(holdout.maxDrawdown)}</span>],
          [
            `p-value (${TEST_WORDING[hypothesis.significanceTest].title.toLowerCase()})`,
            <span className="qf-num">{probability(holdout.pValue)}</span>,
          ],
        ]}
      />
    </QF.Panel>
  );
}

export function RunPanel({ run }: { run: RunSummary }) {
  return (
    <QF.Panel title="Run" icon="run">
      <KeyValues
        rows={[
          ['Code at', <code className="qf-code">{sha(run.gitSha)}</code>],
          ['Written', day(run.generatedAt)],
          ['Data source', <code className="qf-code">{run.dataSource}</code>],
          ['First position', run.firstPosition ? <span className="qf-num">{run.firstPosition}</span> : '—'],
          ['Seed', <span className="qf-num">{run.seed}</span>],
          ['Run id', <span className="qf-num" style={{ fontSize: 11 }}>{run.runId}</span>],
        ]}
      />
    </QF.Panel>
  );
}
