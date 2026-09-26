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
  '/api/hypotheses/demo_select': captured.select,
  '/api/hypotheses/demo_select/equity': captured.momentumEquity,
  '/api/hypotheses/demo_select/trades': captured.momentumTrades,
  '/api/hypotheses/demo_portfolio': captured.portfolio,
  '/api/hypotheses/demo_portfolio/equity': captured.momentumEquity,
  '/api/hypotheses/demo_portfolio/trades': captured.momentumTrades,
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
    expect(within(panel('Multiple testing')).getByText('0.01')).toBeInTheDocument();
    expect(within(panel('Multiple testing')).getByText('Best of 7 no-edge configurations')).toBeInTheDocument();
    expect(within(panel('Contrast')).getByText('−0.44')).toBeInTheDocument();
    expect(within(panel('Regimes')).getAllByRole('row')).toHaveLength(1 + captured.momentum.regimes.length);
  });

  it('splits the P&L by asset class and by instrument, as stored', async () => {
    renderWith('demo_momentum');
    await screen.findByRole('heading', { name: 'Where the P&L came from' });
    const pnl = within(panel('Where the P&L came from'));

    expect(pnl.getByText('By asset class')).toBeInTheDocument();
    expect(pnl.getByText('crypto')).toBeInTheDocument();
    expect(pnl.getByText('By instrument')).toBeInTheDocument();
    expect(pnl.getByText('btc-usdt')).toBeInTheDocument();
    expect(pnl.getByText('eth-usdt')).toBeInTheDocument();
  });

  it('names the significance test the criterion chose', async () => {
    const detail = structuredClone(captured.momentum);
    detail.run!.permutation.test = 'random_portfolio';
    renderWith('demo_momentum', { ...ROUTES, '/api/hypotheses/demo_momentum': detail });

    const test = within(await screen.findByRole('heading', { name: 'Random-portfolio test' }).then((h) => h.closest('section')!));
    expect(test.getByText(/random portfolios from each decision's cross-section/)).toBeInTheDocument();
    expect(test.getByText('Beats random portfolios')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Permutation test' })).not.toBeInTheDocument();
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

  it('shows no grid panels for a hypothesis without a grid', async () => {
    renderWith('demo_momentum');
    await screen.findByRole('heading', { name: 'Costs' });

    expect(screen.queryByRole('heading', { name: 'Parameter selection' })).toBeNull();
    expect(screen.queryByRole('heading', { name: /^CPCV of the selection/ })).toBeNull();
  });

  it("shows a grid's yearly choices with each value's Sharpe and the PBO of choosing", async () => {
    renderWith('demo_select');

    const selection = within(await screen.findByRole('heading', { name: 'Parameter selection' }).then((h) => h.closest('section')!));
    const rows = selection.getAllByRole('row');
    expect(rows).toHaveLength(1 + 3); // 2020, 2021, 2022
    expect(within(rows[0]).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Year', '30', '90', '180', 'Chosen']);
    expect(rows[1]).toHaveTextContent('2020');
    expect(within(rows[1]).getByText('−0.08').tagName).toBe('B'); // the chosen value's Sharpe
    expect(rows[1]).toHaveTextContent('180');
    expect(selection.getByText(/PBO of choosing from the grid \(CSCV, 16 blocks, 12,870 splits, .*\): 0\.88/)).toBeInTheDocument();
  });

  it('shows the CPCV paths and, as the frozen gate, the verdict it gives', async () => {
    renderWith('demo_select');

    const cpcv = within(await screen.findByRole('heading', { name: /^CPCV of the selection/ }).then((h) => h.closest('section')!));
    expect(cpcv.getByText(/10 groups, 2 for testing · purge 1, embargo 11 days · 45 splits, 9 paths/)).toBeInTheDocument();
    expect(cpcv.getByText('failed')).toBeInTheDocument();
    expect(cpcv.getByText(/In-sample gate \(frozen\)\. Rule: median Sharpe of the CPCV paths > 0/)).toBeInTheDocument();
    expect(cpcv.getByText('30 37.8%, 90 0.0%, 180 62.2%')).toBeInTheDocument();
    expect(screen.getByText(/CPCV failed; holdout inconclusive/)).toBeInTheDocument();
    expect(within(panel(/^Walk-forward/)).getByText(/Descriptive only: this hypothesis's frozen in-sample gate is CPCV/)).toBeInTheDocument();
    expect(within(panel('Frozen definition')).getByText('CPCV')).toBeInTheDocument();
  });

  it("shows a portfolio's sleeves: correlations, weights and each rule's Sharpe", async () => {
    renderWith('demo_portfolio');

    const correlations = within(
      await screen.findByRole('heading', { name: 'Sleeve correlations (daily net returns)' }).then((h) => h.closest('section')!),
    );
    expect(correlations.getByText('demo_momentum ~ demo_reversal')).toBeInTheDocument();
    expect(within(panel('Sleeve weights (inverse_volatility, monthly)')).getByText('diversification ratio (median)')).toBeInTheDocument();
    expect(within(panel('Net Sharpe by allocation rule and of each sleeve alone')).getByText('inverse_volatility (frozen)')).toBeInTheDocument();
    expect(within(panel('Frozen definition')).getByText('demo_momentum, demo_reversal, demo_pairs')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Parameter selection' })).toBeNull();
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
