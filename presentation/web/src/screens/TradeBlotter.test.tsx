import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { captured, stubApi } from '../test/api';
import { PAGE_SIZE, TradeBlotter } from './TradeBlotter';

function renderWith(page = captured.momentumTrades) {
  const api = stubApi({ '/api/hypotheses/demo_momentum/trades': page });
  vi.stubGlobal('fetch', api.fetch);
  render(<TradeBlotter id="demo_momentum" instruments={['btc-usdt', 'eth-usdt']} />);
  return api;
}

const query = (url: string) => Object.fromEntries(new URL(url, 'http://test').searchParams);

describe('TradeBlotter', () => {
  it('shows the first page by entry date with the total the API counted', async () => {
    const api = renderWith();

    const table = await screen.findByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(1 + captured.momentumTrades.items.length);
    expect(screen.getByText(`1–${captured.momentumTrades.items.length} of ${captured.momentumTrades.total}`)).toBeInTheDocument();
    expect(query(api.requested[0])).toEqual({ sort: 'entryTs', order: 'asc', offset: '0', limit: String(PAGE_SIZE) });
  });

  it('asks the API for the next page', async () => {
    const api = renderWith();
    await screen.findByRole('table');

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    expect(query(api.requested.at(-1)!)).toMatchObject({ offset: String(PAGE_SIZE) });
  });

  it('sorts by a column, then reverses it on a second click', async () => {
    const api = renderWith();
    await screen.findByRole('table');

    await userEvent.click(screen.getByRole('button', { name: 'Sort by Net P&L' }));
    expect(query(api.requested.at(-1)!)).toMatchObject({ sort: 'netPnl', order: 'asc', offset: '0' });
    await screen.findByRole('table');
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Net P&L' }));
    expect(query(api.requested.at(-1)!)).toMatchObject({ sort: 'netPnl', order: 'desc' });
  });

  it('filters by instrument and side from the first page', async () => {
    const api = renderWith();
    await screen.findByRole('table');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    await screen.findByRole('table');

    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Instrument' }), 'eth-usdt');
    await screen.findByRole('table');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Side' }), 'short');

    expect(query(api.requested.at(-1)!)).toMatchObject({ instrument: 'eth-usdt', side: 'short', offset: '0' });
  });

  it('says so when no trade matches', async () => {
    renderWith({ total: 0, offset: 0, limit: PAGE_SIZE, items: [] });

    expect(await screen.findByText('No trades match these filters.')).toBeInTheDocument();
  });
});
