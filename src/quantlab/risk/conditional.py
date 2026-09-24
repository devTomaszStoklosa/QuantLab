from collections.abc import Callable, Mapping
from datetime import date
from itertools import pairwise

import numpy as np
from pydantic import BaseModel

from quantlab.backtest.run import BacktestRun
from quantlab.reporting.metrics import cagr, sharpe, sortino


class RegimeMetrics(BaseModel):
    label: str
    days: int
    cagr: float | None
    sharpe: float | None
    sortino: float | None


def _defined(metric: Callable[[], float]) -> float | None:
    try:
        return metric()
    except ValueError:
        return None


def _regime_metrics(label: str, returns: list[float], periods_per_year: int) -> RegimeMetrics:
    equity = np.cumprod([1.0, *(1.0 + r for r in returns)]).tolist()
    return RegimeMetrics(
        label=label,
        days=len(returns),
        cagr=_defined(lambda: cagr(equity, periods_per_year)),
        sharpe=_defined(lambda: sharpe(returns, periods_per_year)),
        sortino=_defined(lambda: sortino(returns, periods_per_year)),
    )


def regime_conditional_metrics(
    run: BacktestRun, labels: Mapping[date, str], periods_per_year: int
) -> dict[str, RegimeMetrics]:
    """Net daily returns of a run grouped by regime (REQ-051).

    Each day's return is labeled with the regime as of the day before - when the
    position was chosen. Labeling it with the same day's regime would be
    circular: a large move makes that day both high-volatility and high-return.

    Counting starts at the first held position, as in walk-forward, so the
    warm-up does not dilute any regime. Max drawdown is not reported: days of
    one regime are scattered in time, and a drawdown across them is not a loss
    anyone experienced. A metric that is undefined for a regime is None.
    """
    snapshots = run.snapshots
    first = next((i for i in range(1, len(snapshots)) if snapshots[i].positions), None)
    if first is None:
        return {}

    returns_by_label: dict[str, list[float]] = {}
    for previous, current in pairwise(snapshots[first - 1 :]):
        if previous.ts not in labels:
            raise ValueError(f"No regime label for {previous.ts}")
        returns_by_label.setdefault(labels[previous.ts], []).append(
            current.equity / previous.equity - 1.0
        )
    return {
        label: _regime_metrics(label, returns, periods_per_year)
        for label, returns in returns_by_label.items()
    }
