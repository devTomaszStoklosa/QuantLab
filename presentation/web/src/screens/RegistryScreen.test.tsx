import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { captured, stubApi } from '../test/api';
import { RegistryScreen } from './RegistryScreen';

function renderWith(routes: Record<string, unknown>) {
  vi.stubGlobal('fetch', stubApi(routes).fetch);
  return render(<RegistryScreen />);
}

describe('RegistryScreen', () => {
  it('lists every hypothesis with a link, its status and its holdout state', async () => {
    renderWith({ '/api/hypotheses': captured.registry });

    const table = await screen.findByRole('table');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getByRole('link').textContent)).toEqual([
      'demo_momentum',
      'demo_reversal',
      'demo_pairs',
    ]);
    expect(within(rows[0]).getByRole('link')).toHaveAttribute('href', '#/h/demo_momentum');
    expect(rows[0]).toHaveTextContent('Rejected');
    expect(rows[0]).toHaveTextContent('Opened · inconclusive');
    expect(rows[2]).toHaveTextContent('Sealed');
  });

  it('shows the Sharpe the API returned, a dash and no chart without a run', async () => {
    renderWith({ '/api/hypotheses': captured.registry });

    const rows = within(await screen.findByRole('table')).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('−0.68');
    expect(rows[1]).toHaveTextContent('no runs yet');
    expect(rows[1]).toHaveTextContent('—');
    expect(rows[1].querySelector('svg.qf-spark')).toBeNull();
    expect(rows[2].querySelector('svg.qf-spark')).not.toBeNull();
  });

  it('warns that synthetic runs are not a research result', async () => {
    renderWith({ '/api/hypotheses': captured.registry });

    expect(await screen.findByText('Synthetic data, not a research result')).toBeInTheDocument();
  });

  it('does not warn about data from a market source', async () => {
    const binance = captured.registry.map((h) => ({ ...h, dataSource: h.hasRun ? 'binance' : null }));
    renderWith({ '/api/hypotheses': binance });

    await screen.findByRole('table');
    expect(screen.queryByText('Synthetic data, not a research result')).toBeNull();
  });

  it('filters by status through the tabs, with counts from the registry', async () => {
    renderWith({ '/api/hypotheses': captured.registry });
    const rejected = await screen.findByRole('tab', { name: /Rejected/ });
    expect(rejected).toHaveTextContent('1');

    await userEvent.click(rejected);

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent('demo_momentum');
    await userEvent.click(screen.getByRole('tab', { name: /Confirmed/ }));
    expect(screen.getByText('No hypothesis has this status.')).toBeInTheDocument();
  });

  it('explains how to fill an empty store', async () => {
    renderWith({ '/api/hypotheses': [] });

    expect(await screen.findByText('No hypotheses in the results store')).toBeInTheDocument();
    expect(screen.getByText('uv run quantlab registry')).toBeInTheDocument();
  });

  it('shows an API error as a danger callout with its title', async () => {
    renderWith({
      '/api/hypotheses': new Response(
        JSON.stringify({ title: 'Results store has an incompatible schema version', status: 503 }),
        { status: 503, headers: { 'Content-Type': 'application/problem+json' } },
      ),
    });

    expect(await screen.findByText('Results store has an incompatible schema version')).toBeInTheDocument();
  });
});
