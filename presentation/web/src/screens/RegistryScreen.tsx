import { useState } from 'react';
import { api, type HypothesisSummary, type Status } from '../api';
import { Command, Disclaimer, ErrorNotice, Loading, PageHead, SyntheticNotice } from '../components';
import { QF, type Column } from '../design-system';
import { isSynthetic, range, ratio, sha } from '../format';
import { useResource } from '../resource';
import { href } from '../route';

type Tab = 'all' | Status;

const TABS: Array<{ value: Tab; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'proposed', label: 'Proposed' },
  { value: 'testing', label: 'Testing' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'inconclusive', label: 'Inconclusive' },
];

type Row = HypothesisSummary & { id: string };

const COLUMNS: Column<Row>[] = [
  {
    key: 'hypothesis',
    label: 'Hypothesis',
    render: (id: string, row) => (
      <div>
        <a className="qf-num" style={{ fontWeight: 600 }} href={href.hypothesis(id)}>
          {id}
        </a>
        <div className="qf-muted" style={{ fontSize: 12 }}>
          {row.strategy}
        </div>
      </div>
    ),
  },
  { key: 'status', label: 'Status', render: (status: Status) => <QF.StatusBadge status={status} /> },
  {
    key: 'trainingStart',
    label: 'Training',
    render: (_: string, row) => <span className="qf-num ql-nowrap">{range(row.trainingStart, row.trainingEnd)}</span>,
  },
  {
    key: 'sparkline',
    label: 'Equity, training',
    render: (series: number[], row) =>
      row.hasRun && series.length > 1 ? (
        <QF.Sparkline series={series} width={104} height={22} />
      ) : (
        <span className="qf-muted" style={{ fontSize: 12 }}>
          no runs yet
        </span>
      ),
  },
  {
    key: 'trainingSharpe',
    label: 'Sharpe, training',
    numeric: true,
    format: (value: number | null) => ratio(value),
    tone: (value: number | null) => (value == null ? 'dim' : value < 0 ? 'loss' : null),
  },
  {
    key: 'holdout',
    label: 'Holdout',
    render: (_: unknown, row) =>
      row.holdout ? (
        <QF.PartitionTag partition="holdout" sealed={false}>
          Opened · {row.holdout.verdict}
        </QF.PartitionTag>
      ) : (
        <QF.PartitionTag partition="holdout">Sealed</QF.PartitionTag>
      ),
  },
  { key: 'trialsOnSameData', label: 'Trials on its data', numeric: true },
  {
    key: 'frozenAtCommit',
    label: 'Frozen at',
    render: (commit: string) => <code className="qf-code">{sha(commit)}</code>,
  },
];

export function RegistryScreen() {
  const registry = useResource('hypotheses', api.hypotheses);
  const [tab, setTab] = useState<Tab>('all');

  if (registry.state === 'loading') return <Loading />;
  if (registry.state === 'failed') return <ErrorNotice error={registry.error} />;

  const hypotheses = registry.data;
  const head = (
    <PageHead
      eyebrow={[...new Set(hypotheses.map((h) => h.universe))].join(' · ') || 'Results store'}
      title="Hypothesis registry"
      sub="Every hypothesis is frozen in git before any run reads its data. Rejected and inconclusive results count as findings too."
    />
  );
  if (hypotheses.length === 0) {
    return (
      <>
        {head}
        <QF.Callout tone="info" title="No hypotheses in the results store">
          Write the registry from the committed definitions with <Command>uv run quantlab registry</Command>, or
          run a hypothesis with <Command>uv run quantlab run &lt;id&gt;</Command>.
        </QF.Callout>
        <Disclaimer />
      </>
    );
  }

  const count = (status: Status) => hypotheses.filter((h) => h.status === status).length;
  const rows: Row[] = hypotheses
    .filter((h) => tab === 'all' || h.status === tab)
    .map((h) => ({ ...h, id: h.hypothesis }));
  return (
    <>
      {head}
      {hypotheses.some((h) => isSynthetic(h.dataSource)) && <SyntheticNotice />}
      <QF.MetricStrip
        columns={5}
        items={[
          { label: 'Registered', value: String(hypotheses.length), hint: 'committed definitions' },
          { label: 'Confirmed', value: String(count('confirmed')), hint: 'both gates passed' },
          { label: 'Rejected', value: String(count('rejected')), hint: 'a gate failed' },
          { label: 'Inconclusive', value: String(count('inconclusive')), hint: 'no evidence either way' },
          { label: 'Testing', value: String(count('testing')), hint: `${count('proposed')} not run yet` },
        ]}
      />
      <QF.Panel flush>
        <div style={{ padding: '0 16px' }}>
          <QF.Tabs
            value={tab}
            onChange={(value) => setTab(value as Tab)}
            items={TABS.map((t) => ({
              ...t,
              count: t.value === 'all' ? hypotheses.length : count(t.value),
            }))}
          />
        </div>
        {rows.length === 0 ? (
          <p className="qf-muted" style={{ padding: 16 }}>
            No hypothesis has this status.
          </p>
        ) : (
          <QF.DataTable rows={rows} columns={COLUMNS} />
        )}
      </QF.Panel>
      <Disclaimer />
    </>
  );
}
