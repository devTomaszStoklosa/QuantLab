from typing import Literal

from pydantic import BaseModel

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.reporting.metrics import cagr, calmar, max_drawdown, sharpe, sortino

# Costs mostly shift the mean return and barely move volatility, so a Sharpe
# difference is the cost drag measured in units of result volatility - the
# "small relative to result volatility" test in 02-spec.md's business rules.
ROBUST_SHARPE_DIFFERENCE = 0.1


class RunMetrics(BaseModel):
    cost_model_name: str
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float


class CostSensitivity(BaseModel):
    lower_cost_model: str
    higher_cost_model: str
    sharpe_difference: float
    cagr_sign_flip: bool
    verdict: Literal["robust", "cost-dependent"]


def run_metrics(run: BacktestRun, periods_per_year: int) -> RunMetrics:
    equity = [snapshot.equity for snapshot in run.snapshots]
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    return RunMetrics(
        cost_model_name=run.cost_model_name,
        cagr=cagr(equity, periods_per_year),
        sharpe=sharpe(returns, periods_per_year),
        sortino=sortino(returns, periods_per_year),
        calmar=calmar(equity, periods_per_year),
        max_drawdown=max_drawdown(equity),
    )


def cost_sensitivity(lower_cost: RunMetrics, higher_cost: RunMetrics) -> CostSensitivity:
    """Robust only if the Sharpe gap is small and CAGR keeps its sign.

    02-spec.md covers "small -> robust" and "large, flips sign -> cost-dependent"
    but not "large without a sign flip"; that case is treated as cost-dependent,
    erring toward reporting a limitation rather than hiding one.
    """
    sharpe_difference = lower_cost.sharpe - higher_cost.sharpe
    cagr_sign_flip = (lower_cost.cagr > 0) != (higher_cost.cagr > 0)
    robust = abs(sharpe_difference) < ROBUST_SHARPE_DIFFERENCE and not cagr_sign_flip
    return CostSensitivity(
        lower_cost_model=lower_cost.cost_model_name,
        higher_cost_model=higher_cost.cost_model_name,
        sharpe_difference=sharpe_difference,
        cagr_sign_flip=cagr_sign_flip,
        verdict="robust" if robust else "cost-dependent",
    )
