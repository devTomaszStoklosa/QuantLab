from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from quantlab.backtest.run import BacktestRun
from quantlab.reporting.metrics import (
    annualized_turnover,
    cagr,
    calmar,
    max_drawdown,
    sharpe,
    sortino,
)

# Costs mostly shift the mean return and barely move volatility, so a Sharpe
# difference is the cost drag measured in units of result volatility - the
# "small relative to result volatility" test in 02-spec.md's business rules.
ROBUST_SHARPE_DIFFERENCE = 0.1


class RunMetrics(BaseModel):
    """A run's metrics; None where one is undefined (e.g. Sharpe of a run that never traded)."""

    cost_model_name: str
    cagr: float | None
    sharpe: float | None
    sortino: float | None
    calmar: float | None
    max_drawdown: float | None
    turnover: float  # multiple of equity traded per year, counted from the first trade


class CostSensitivity(BaseModel):
    lower_cost_model: str
    higher_cost_model: str
    sharpe_difference: float | None
    cagr_sign_flip: bool | None
    verdict: Literal["robust", "cost-dependent", "undefined"]


def _defined(metric: Callable[[], float]) -> float | None:
    try:
        return metric()
    except ValueError:
        return None


def run_metrics(run: BacktestRun, periods_per_year: int) -> RunMetrics:
    """Metrics of the whole run; turnover only from the first trade, so the
    warm-up before any signal does not dilute it (as in walk-forward).
    """
    equity = [snapshot.equity for snapshot in run.snapshots]
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    traded = [sum(snapshot.traded.values()) for snapshot in run.snapshots[1:]]
    first_trade = next((i for i, value in enumerate(traded) if value > 0.0), None)
    return RunMetrics(
        cost_model_name=run.cost_model_name,
        cagr=_defined(lambda: cagr(equity, periods_per_year)),
        sharpe=_defined(lambda: sharpe(returns, periods_per_year)),
        sortino=_defined(lambda: sortino(returns, periods_per_year)),
        calmar=_defined(lambda: calmar(equity, periods_per_year)),
        max_drawdown=_defined(lambda: max_drawdown(equity)),
        turnover=(
            0.0
            if first_trade is None
            else annualized_turnover(traded[first_trade:], periods_per_year)
        ),
    )


def cost_sensitivity(lower_cost: RunMetrics, higher_cost: RunMetrics) -> CostSensitivity:
    """Robust only if the Sharpe gap is small and CAGR keeps its sign.

    02-spec.md covers "small -> robust" and "large, flips sign -> cost-dependent"
    but not "large without a sign flip"; that case is treated as cost-dependent,
    erring toward reporting a limitation rather than hiding one. Without a
    Sharpe or CAGR for both runs (e.g. no trades) there is nothing to compare.
    """
    if None in (lower_cost.sharpe, higher_cost.sharpe, lower_cost.cagr, higher_cost.cagr):
        return CostSensitivity(
            lower_cost_model=lower_cost.cost_model_name,
            higher_cost_model=higher_cost.cost_model_name,
            sharpe_difference=None,
            cagr_sign_flip=None,
            verdict="undefined",
        )
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
