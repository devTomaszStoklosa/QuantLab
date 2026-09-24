import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { captured, stubApi } from '../test/api';
import { HypothesisScreen } from './HypothesisScreen';

const ROUTES = {
  '/api/hypotheses/demo_momentum': captured.momentum,
  '/api/hypotheses/demo_momentum/equity': captured.momentumEquity,
  '/api/hypotheses/demo_momentum/trades': captured.momentumTrades,
  '/api/hypotheses/demo_reversal': captured.reversal,
  '/api/hypotheses/demo_pairs': captured.pairs,
  '/api/hypotheses/demo_pairs/equity': captured.momentumEquity,
  '/api/hypotheses/demo_pairs/trades': captured.momentumTrades,
};

function renderWith(id: string, routes: Record<string, unknown> = ROUTES) {
  const api = stubApi(routes);
  vi.stubGlobal('fetch', api.fetch);
  render(<HypothesisScreen id={id} />);
  return api;
}

const panel = (title: string | RegExp) => screen.getByRole('heading', { name: title }).closest('section')!;

describe('HypothesisScreen', () => {
  it('heads the page with the hypothesis, its status and the commit that froze it', async () => {
    renderWith('demo_momentum');

    expect(await screen.findByRole('heading', { name: 'demo_momentum' })).toBeInTheDocument();
    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0);
    expect(screen.getAllByText(captured.momentum.hypothesis.frozenAtCommit.slice(0, 7)).length).toBeGreaterThan(0);
  });

  it('states the verdict from the recorded gates once the holdout is open', async () => {
    renderWith('demo_momentum');

    expect(await screen.findByText(/Walk-forward failed; holdout inconclusive \(net Sharpe 1\.50, p = 0\.547\)/)).toBeInTheDocument();
    expect(screen.queryByText('No verdict until the frozen holdout is opened')).toBeNull();
  });

  it('draws the equity curve with the drawdowns the API returned', async () => {
    renderWith('demo_momentum');

    const chart = await screen.findByRole('img', { name: /Equity curve of the training run/ });
    expect(chart).toHaveTextContent(/max DD −96\.2%/);
  });

  it('shows each evidence table with the API numbers, formatted', async () => {
    renderWith('demo_momentum');
    await screen.findByRole('heading', { name: 'Costs' });

    expect(within(panel('Costs')).getAllByRole('row')).toHaveLength(1 + captured.momentum.metrics.length);
    expect(within(panel('Costs')).getByText('cost-dependent')).toBeInTheDocument();
    expect(within(panel(/^Walk-forward/)).getByText('Aggregate')).toBeInTheDocument();
    expect(within(panel(/^Walk-forward/)).getByText('failed')).toBeInTheDocument();
    expect(within(panel('Permutation test')).getByText('0.898')).toBeInTheDocument();
    expect(within(panel('Multiple testing')).getByText('0.02')).toBeInTheDocument();
    expect(within(panel('Contrast')).getByText('−0.44')).toBeInTheDocument();
    expect(within(panel('Regimes')).getAllByRole('row')).toHaveLength(1 + captured.momentum.regimes.length);
  });

  it('shows the year totals quantlab computed, not compounded months', async () => {
    const detail = structuredClone(captured.momentum);
    detail.yearly[0].netReturn = 0.1234; // deliberately not the product of its months
    renderWith('demo_momentum', { ...ROUTES, '/api/hypotheses/demo_momentum': detail });

    const heatmap = within(await screen.findByRole('heading', { name: 'Monthly net returns' }).then((h) => h.closest('section')!));
    expect(heatmap.getByText('12.3')).toBeInTheDocument();
  });

  it('lays out the frozen definition, the opened seal and the run', async () => {
    renderWith('demo_momentum');
    await screen.findByRole('heading', { name: 'Frozen definition' });

    expect(within(panel('Frozen definition')).getByText('lookback_days')).toBeInTheDocument();
    expect(screen.getAllByText('Holdout opened')).toHaveLength(2); // header tag and seal
    expect(screen.getByText('0 of 1 look left')).toBeInTheDocument();
    expect(within(panel('Run')).getByText('synthetic')).toBeInTheDocument();
  });

  it('warns that a synthetic run is not a research result', async () => {
    renderWith('demo_momentum');

    expect(await screen.findByText('Synthetic data, not a research result')).toBeInTheDocument();
  });

  it('says a sealed hypothesis has no verdict and names the command that opens it', async () => {
    renderWith('demo_pairs');

    expect(await screen.findByText('No verdict until the frozen holdout is opened')).toBeInTheDocument();
    expect(screen.getByText('uv run quantlab open-holdout demo_pairs')).toBeInTheDocument();
    expect(screen.getByText('1 of 1 look left')).toBeInTheDocument();
  });

  it("shows a pairs run's training diagnostics", async () => {
    renderWith('demo_pairs');

    const diagnostics = within(await screen.findByRole('heading', { name: 'Cointegration of eth-usdt on btc-usdt' }).then((h) => h.closest('section')!));
    expect(diagnostics.getByText('hedge ratio')).toBeInTheDocument();
    expect(diagnostics.getByText('1096')).toBeInTheDocument();
  });

  it('shows no runs yet, and fetches no equity or trades, without a run', async () => {
    const api = renderWith('demo_reversal');

    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    expect(screen.getByText('uv run quantlab run demo_reversal')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /Equity curve/ })).toBeNull();
    expect(api.requested).toEqual(['/api/hypotheses/demo_reversal']);
  });

  it('shows the API problem for an unknown hypothesis', async () => {
    renderWith('momentum_v1', {
      '/api/hypotheses/momentum_v1': new Response(
        JSON.stringify({ title: "Unknown hypothesis 'momentum_v1'", status: 404 }),
        { status: 404, headers: { 'Content-Type': 'application/problem+json' } },
      ),
    });

    expect(await screen.findByText("Unknown hypothesis 'momentum_v1'")).toBeInTheDocument();
  });
});
