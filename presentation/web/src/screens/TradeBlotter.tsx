import { useState } from 'react';
import { api, type Trade, type TradeQuery, type TradeSort } from '../api';
import { ErrorNotice, Loading } from '../components';
import { QF, type Column } from '../design-system';
import { cost, percent, pnl, price } from '../format';
import { useResource } from '../resource';

export const PAGE_SIZE = 25;

type Row = Trade & { id: number };

const tone = (value: number) => (value < 0 ? 'loss' : value > 0 ? 'gain' : null);

/** The run's trade ledger: filtered, sorted and paged by the API (REQ-742). */
export function TradeBlotter({ id, instruments }: { id: string; instruments: string[] }) {
  const [instrument, setInstrument] = useState('');
  const [side, setSide] = useState<'' | 'long' | 'short'>('');
  const [sort, setSort] = useState<TradeSort>('entryTs');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [offset, setOffset] = useState(0);
  const query: TradeQuery = {
    instrument: instrument || undefined,
    side: side || undefined,
    sort,
    order,
    offset,
    limit: PAGE_SIZE,
  };
  const page = useResource(`trades:${id}:${JSON.stringify(query)}`, () => api.trades(id, query));

  function sortBy(column: TradeSort) {
    if (column === sort) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(column);
      setOrder('asc');
    }
    setOffset(0);
  }

  const header = (column: TradeSort, label: string) => (
    <button type="button" className="ql-sort" onClick={() => sortBy(column)} aria-label={`Sort by ${label}`}>
      {label}
      {sort === column ? (order === 'asc' ? ' ↑' : ' ↓') : ''}
    </button>
  );

  const columns: Column<Row>[] = [
    { key: 'tradeId', label: '#', numeric: true, tone: () => 'dim' },
    { key: 'instrumentId', label: header('instrumentId', 'Instrument') },
    { key: 'side', label: 'Side' },
    { key: 'entryTs', label: header('entryTs', 'Entry'), render: (v: string) => <span className="qf-num ql-nowrap">{v}</span> },
    { key: 'entryPrice', label: 'Entry price', numeric: true, format: (v: number) => price(v) },
    {
      key: 'exitTs',
      label: header('exitTs', 'Exit'),
      render: (v: string, row) => (
        <span className="qf-num ql-nowrap" title={row.openAtEnd ? 'Still held when the run ended' : undefined}>
          {v}
          {row.openAtEnd ? ' *' : ''}
        </span>
      ),
    },
    { key: 'exitPrice', label: 'Exit price', numeric: true, format: (v: number) => price(v) },
    { key: 'size', label: header('size', 'Size'), numeric: true, format: (v: number) => percent(v) },
    { key: 'grossPnl', label: header('grossPnl', 'Gross P&L'), numeric: true, format: (v: number) => pnl(v), tone },
    { key: 'costs', label: header('costs', 'Costs'), numeric: true, format: (v: number) => cost(v) },
    { key: 'netPnl', label: header('netPnl', 'Net P&L'), numeric: true, format: (v: number) => pnl(v), tone },
    { key: 'holdingDays', label: header('holdingDays', 'Days'), numeric: true },
    { key: 'regimeAtEntry', label: 'Regime at entry' },
  ];

  const filters = (
    <div className="qf-row">
      <QF.Select
        style={{ width: 'auto' }}
        aria-label="Instrument"
        value={instrument}
        onChange={(event) => {
          setInstrument(event.target.value);
          setOffset(0);
        }}
        options={[{ value: '', label: 'All instruments' }, ...instruments.map((i) => ({ value: i, label: i }))]}
      />
      <QF.Select
        style={{ width: 'auto' }}
        aria-label="Side"
        value={side}
        onChange={(event) => {
          setSide(event.target.value as '' | 'long' | 'short');
          setOffset(0);
        }}
        options={[
          { value: '', label: 'Both sides' },
          { value: 'long', label: 'Long' },
          { value: 'short', label: 'Short' },
        ]}
      />
    </div>
  );

  let body;
  let footer = null;
  if (page.state === 'loading') {
    body = <div style={{ padding: 16 }}><Loading /></div>;
  } else if (page.state === 'failed') {
    body = <div style={{ padding: 16 }}><ErrorNotice error={page.error} /></div>;
  } else if (page.data.items.length === 0) {
    body = <p className="qf-muted" style={{ padding: 16 }}>No trades match these filters.</p>;
  } else {
    const { total, items } = page.data;
    body = <QF.DataTable dense rows={items.map((t) => ({ ...t, id: t.tradeId }))} columns={columns} />;
    footer = (
      <div className="qf-row" style={{ justifyContent: 'space-between' }}>
        <span className="qf-num">
          {offset + 1}–{offset + items.length} of {total}
        </span>
        <span className="qf-row">
          <QF.Button size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            Previous
          </QF.Button>
          <QF.Button size="sm" disabled={offset + items.length >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
            Next
          </QF.Button>
        </span>
      </div>
    );
  }
  return (
    <QF.Panel
      title="Trades"
      icon="attribution"
      subtitle="Trade ledger of the training run · prices adjusted for corporate actions · P&L and costs as percent of initial equity · * still held at the end"
      actions={filters}
      flush
      footer={footer}
    >
      {body}
    </QF.Panel>
  );
}
