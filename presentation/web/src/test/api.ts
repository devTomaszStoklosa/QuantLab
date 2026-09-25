// Responses of the API on the synthetic results store (presentation/fixtures/results),
// captured by the .NET UiFixtureTests, which fail when they no longer match the API.
import type { EquityPoint, HypothesisDetail, HypothesisSummary, TradePage } from '../api';
import momentumEquity from './api/demo_momentum-equity.json';
import momentumTrades from './api/demo_momentum-trades.json';
import momentum from './api/demo_momentum.json';
import pairs from './api/demo_pairs.json';
import reversal from './api/demo_reversal.json';
import select from './api/demo_select.json';
import registry from './api/registry.json';

export const captured = {
  registry: registry as HypothesisSummary[],
  momentum: momentum as HypothesisDetail,
  reversal: reversal as HypothesisDetail,
  pairs: pairs as HypothesisDetail,
  select: select as HypothesisDetail,
  momentumEquity: momentumEquity as EquityPoint[],
  momentumTrades: momentumTrades as TradePage,
};

/** A fetch stub answering each API path with a body, 404 problem otherwise; records requested URLs. */
export function stubApi(routes: Record<string, unknown>) {
  const requested: string[] = [];
  const fetch = async (input: string | URL | Request) => {
    const url = String(input);
    requested.push(url);
    const path = url.split('?')[0];
    const body = routes[url] ?? routes[path];
    if (body === undefined) {
      return new Response(JSON.stringify({ title: `No stub for ${url}`, status: 404 }), {
        status: 404,
        headers: { 'Content-Type': 'application/problem+json' },
      });
    }
    if (body instanceof Response) return body;
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  };
  return { fetch, requested };
}
