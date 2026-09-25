"""What a portfolio's training report shows besides its run (q9, REQ-940, REQ-941).

Descriptive only: sleeve correlations, the weights the frozen rule gave, the
diversification ratio, and the net Sharpe of the portfolio under every
allocation rule and of each sleeve alone - all over the training period and
from the same sleeve history the run used.
"""

from datetime import date
from itertools import combinations

import numpy as np

from quantlab.backtest.run import trading_dates
from quantlab.backtest.sizing import CarriedWeights
from quantlab.core.data.provider import PriceBar
from quantlab.costs.base import CostModel
from quantlab.portfolio.allocation import AllocationRule
from quantlab.reporting.metrics import sharpe
from quantlab.strategy.portfolio import SleeveHistory, StrategyPortfolio
from quantlab.strategy.selected_parameter import net_returns


def _month_starts(start: date, end: date) -> list[date]:
    months, month = [], start.replace(day=1)
    while month <= end:
        months.append(month)
        month = date(month.year + month.month // 12, month.month % 12 + 1, 1)
    return months


def _sharpe(returns: np.ndarray | list[float], periods_per_year: int) -> float | None:
    try:
        return sharpe(list(returns), periods_per_year)
    except ValueError:
        return None  # fewer than two returns, or no variance: no position


def portfolio_report(
    history: SleeveHistory,
    rules: dict[str, AllocationRule],
    frozen: str,
    window_days: int,
    min_window_days: int,
    cost_model: CostModel,
    bars: dict[str, list[PriceBar]],
    start: date,
    end: date,
    periods_per_year: int,
) -> dict[str, dict[str, float | None]]:
    """Title -> label -> value, in display order."""
    names = history.names
    # The sleeves' own daily net returns over the training period, from the anchored runs.
    periods = len(trading_dates(bars, start, end)) - 1
    anchored = history.returns(bars, date.fromordinal(end.toordinal() + 1))
    sleeves = anchored[-periods:] if periods > 0 else anchored[:0]
    with np.errstate(divide="ignore", invalid="ignore"):
        correlation = np.corrcoef(sleeves, rowvar=False) if len(sleeves) >= 2 else None
    correlations = {
        f"{names[a]} ~ {names[b]}": (
            None
            if correlation is None or not np.isfinite(correlation[a, b])
            else float(correlation[a, b])
        )
        for a, b in combinations(range(len(names)), 2)
    }

    portfolio = StrategyPortfolio(history, rules[frozen], window_days, min_window_days)
    records = [portfolio.allocation(bars, month) for month in _month_starts(start, end)]
    allocated = [record for record in records if sum(record.weights.values()) > 0.0]
    weights: dict[str, float | None] = {}
    for name in names:
        values = [record.weights[name] for record in allocated]
        weights[f"{name} mean"] = float(np.mean(values)) if values else None
        weights[f"{name} min"] = min(values) if values else None
        weights[f"{name} max"] = max(values) if values else None
    ratios = [r.diversification_ratio for r in allocated if r.diversification_ratio is not None]
    weights["months allocated"] = float(len(allocated))
    weights["diversification ratio (median)"] = float(np.median(ratios)) if ratios else None

    sharpes: dict[str, float | None] = {}
    for name, rule in rules.items():
        returns = net_returns(
            StrategyPortfolio(history, rule, window_days, min_window_days),
            cost_model,
            bars,
            start,
            end,
            sizer=CarriedWeights(),
        )
        label = f"{name} (frozen)" if name == frozen else name
        sharpes[label] = _sharpe(returns, periods_per_year)
    for index, name in enumerate(names):
        sharpes[f"{name} alone"] = _sharpe(sleeves[:, index], periods_per_year)

    return {
        "Sleeve correlations (daily net returns)": correlations,
        f"Sleeve weights ({frozen}, monthly)": weights,
        "Net Sharpe by allocation rule and of each sleeve alone": sharpes,
    }
