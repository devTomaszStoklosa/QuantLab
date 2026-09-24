// Client of the read-only QuantLab API (presentation/QuantLab.Api). Types mirror its JSON:
// every number arrives computed by quantlab, and null means undefined, never 0.

export type Status = 'proposed' | 'testing' | 'confirmed' | 'rejected' | 'inconclusive';
export type HoldoutVerdict = 'passed' | 'inconclusive' | 'rejected';

export interface StoreHealth {
  resultsPath: string;
  exists: boolean;
  schemaVersion: number | null;
  compatible: boolean;
}

export interface HoldoutRecord {
  openedAt: string;
  openedAtCommit: string;
  costModel: string;
  cagr: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  maxDrawdown: number | null;
  pValue: number | null;
  verdict: HoldoutVerdict;
}

// Which test gave a p-value (q5, REQ-563): timing (day shuffle) or selection.
export type SignificanceTest = 'day_shuffle' | 'random_portfolio';

export interface HypothesisSummary {
  hypothesis: string;
  strategy: string;
  universe: string;
  costModel: string;
  parameters: Record<string, unknown>;
  trainingStart: string;
  trainingEnd: string;
  holdoutStart: string;
  holdoutEnd: string;
  criterion: string;
  minSharpe: number;
  maxPValue: number;
  significanceTest: SignificanceTest;
  frozenAtCommit: string;
  registeredAt: string;
  trialsOnSameData: number;
  status: Status;
  hasRun: boolean;
  holdout: HoldoutRecord | null;
  trainingSharpe: number | null;
  sparkline: number[];
  dataSource: string | null;
}

export interface RunSummary {
  runId: string;
  strategy: string;
  strategyParams: Record<string, unknown>;
  universe: string;
  costModel: string;
  start: string;
  end: string;
  firstPosition: string | null;
  seed: number;
  gitSha: string;
  generatedAt: string;
  dataSource: string;
  costSensitivity: { verdict: string; sharpeDifference: number | null; cagrSignFlip: boolean | null };
  walkForward: { passed: boolean | null; rule: string; positiveWindows: number; windowsWithSharpe: number };
  permutation: {
    passed: boolean | null;
    test: SignificanceTest;
    statistic: string;
    count: number;
    seed: number;
    alpha: number;
    activeDays: number;
    lowConfidence: boolean;
    actual: number | null;
    nullMean: number | null;
    nullStd: number | null;
    percentile: number | null;
    pValue: number | null;
    reason: string | null;
  };
  multipleTesting: {
    trials: string[];
    returnsCount: number;
    sharpeAnnualized: number | null;
    psr: number | null;
    dsrThreshold: number | null;
    dsr: number | null;
  };
  contrast: { hypothesis: string; costModel: string; correlation: number | null } | null;
  regimeMethod: string;
  trades: { total: number; openAtEnd: number; winning: number };
}

export interface CostModelMetrics {
  costModel: string;
  cagr: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  maxDrawdown: number | null;
  turnover: number;
  primary: boolean;
}

export interface WalkForwardWindow {
  start: string;
  end: string;
  partial: boolean;
  aggregate: boolean;
  cagr: number | null;
  sharpe: number | null;
  maxDrawdown: number | null;
}

export interface RegimeMetrics {
  regime: string;
  days: number;
  share: number;
  cagr: number | null;
  sharpe: number | null;
  sortino: number | null;
}

export interface MonthlyReturn {
  year: number;
  month: number;
  netReturn: number;
}

export interface YearlyReturn {
  year: number;
  netReturn: number;
}

export interface PnlGroup {
  dimension: 'regime' | 'holding_period';
  key: string;
  trades: number;
  winRate: number;
  totalNetPnl: number;
  meanNetPnl: number;
  medianNetPnl: number;
  worstNetPnl: number;
  bestNetPnl: number;
  costs: number;
}

export interface Diagnostic {
  title: string;
  label: string;
  value: number | null;
}

export interface HypothesisDetail {
  hypothesis: HypothesisSummary;
  run: RunSummary | null;
  metrics: CostModelMetrics[];
  walkForward: WalkForwardWindow[];
  regimes: RegimeMetrics[];
  monthly: MonthlyReturn[];
  yearly: YearlyReturn[];
  pnlGroups: PnlGroup[];
  diagnostics: Diagnostic[];
  tradeInstruments: string[];
}

export interface EquityPoint {
  ts: string;
  equity: number;
  drawdown: number;
}

export interface Trade {
  tradeId: number;
  instrumentId: string;
  side: 'long' | 'short';
  entryTs: string;
  entryPrice: number;
  exitTs: string;
  exitPrice: number;
  size: number;
  grossPnl: number;
  costs: number;
  netPnl: number;
  holdingDays: number;
  regimeAtEntry: string;
  openAtEnd: boolean;
}

export type TradeSort =
  | 'entryTs'
  | 'exitTs'
  | 'instrumentId'
  | 'size'
  | 'grossPnl'
  | 'costs'
  | 'netPnl'
  | 'holdingDays';

export interface TradeQuery {
  instrument?: string;
  side?: 'long' | 'short';
  sort?: TradeSort;
  order?: 'asc' | 'desc';
  offset?: number;
  limit?: number;
}

export interface TradePage {
  total: number;
  offset: number;
  limit: number;
  items: Trade[];
}

/** An API error with the title of its problem+json body. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;

  constructor(status: number, title: string, detail: string | null) {
    super(title);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!response.ok) {
    let title = `${response.status} ${response.statusText}`.trim();
    let detail: string | null = null;
    try {
      const problem = (await response.json()) as { title?: string; detail?: string };
      title = problem.title ?? title;
      detail = problem.detail ?? null;
    } catch {
      // not a problem+json body; keep the status line
    }
    throw new ApiError(response.status, title, detail);
  }
  return (await response.json()) as T;
}

const hypothesisPath = (id: string) => `/api/hypotheses/${encodeURIComponent(id)}`;

export const api = {
  health: () => get<StoreHealth>('/api/health'),
  hypotheses: () => get<HypothesisSummary[]>('/api/hypotheses'),
  hypothesis: (id: string) => get<HypothesisDetail>(hypothesisPath(id)),
  equity: (id: string) => get<EquityPoint[]>(`${hypothesisPath(id)}/equity`),
  trades: (id: string, query: TradeQuery = {}) => {
    const parameters = new URLSearchParams();
    for (const [name, value] of Object.entries(query)) {
      if (value !== undefined && value !== '') {
        parameters.set(name, String(value));
      }
    }
    const search = parameters.toString();
    return get<TradePage>(`${hypothesisPath(id)}/trades${search ? `?${search}` : ''}`);
  },
};
