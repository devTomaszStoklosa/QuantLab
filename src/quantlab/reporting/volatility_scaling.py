"""What a volatility-targeted hypothesis's training report shows besides its run (q11, REQ-1130).

Descriptive only: how large the positions were against their equal-weight
share, and the same strategy without the scaling over the same window, under
the same cost model - the one difference between the two is the position size.
"""

from datetime import date

import numpy as np

from quantlab.backtest.run import trading_dates
from quantlab.backtest.sizing import Sizer
from quantlab.core.data.provider import PriceBar
from quantlab.costs.base import CostModel
from quantlab.reporting.metrics import max_drawdown, sharpe
from quantlab.strategy.base import Strategy
from quantlab.strategy.selected_parameter import net_returns
from quantlab.strategy.volatility_target import VolatilityTargeted

SCALE_TITLE = "Position scale against the equal-weight share"
CONTRAST_TITLE = "Scaled vs unscaled, net of costs"


def _sharpe(returns: list[float], periods_per_year: int) -> float | None:
    try:
        return sharpe(returns, periods_per_year)
    except ValueError:
        return None  # fewer than two returns, or no variance: no position


def _volatility(returns: list[float], periods_per_year: int) -> float | None:
    if len(returns) < 2:
        return None
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def _drawdown(returns: list[float]) -> float | None:
    if not returns:
        return None
    return max_drawdown(np.cumprod(np.concatenate([[1.0], 1.0 + np.asarray(returns)])).tolist())


def scaling_report(
    scaled: VolatilityTargeted,
    sizer: Sizer,
    unscaled: Strategy,
    cost_model: CostModel,
    bars: dict[str, list[PriceBar]],
    start: date | None,
    end: date,
    periods_per_year: int,
) -> dict[str, dict[str, float | None]]:
    """Title -> label -> value, in display order, over [start, end].

    `start` is the first day every instrument can signal (None when no such day
    comes before `end`: every value is then n/a). Scales are those of the
    decisions the engine makes, one per trading day but the last; `unscaled` is
    weighted equally by sign, the engines' default.
    """
    decisions = trading_dates(bars, start, end)[:-1] if start is not None and start < end else []
    scales: dict[str, list[float]] = {instrument_id: [] for instrument_id in sorted(bars)}
    for day in decisions:
        for signal in scaled.generate_signals(bars, day):
            if signal.weight is not None:
                scales[signal.instrument_id].append(signal.weight)

    per_instrument: dict[str, float | None] = {}
    for instrument_id, values in scales.items():
        per_instrument[f"{instrument_id} mean"] = float(np.mean(values)) if values else None
        per_instrument[f"{instrument_id} min"] = min(values) if values else None
        per_instrument[f"{instrument_id} max"] = max(values) if values else None
        per_instrument[f"{instrument_id} share at the cap"] = (
            sum(value == scaled.max_scale for value in values) / len(values) if values else None
        )

    with_scale: list[float] = []
    without_scale: list[float] = []
    if decisions:
        with_scale = net_returns(scaled, cost_model, bars, start, end, sizer=sizer)
        without_scale = net_returns(unscaled, cost_model, bars, start, end)
    contrast = {
        "Sharpe scaled": _sharpe(with_scale, periods_per_year),
        "Sharpe unscaled": _sharpe(without_scale, periods_per_year),
        "volatility scaled": _volatility(with_scale, periods_per_year),
        "volatility unscaled": _volatility(without_scale, periods_per_year),
        "max drawdown scaled": _drawdown(with_scale),
        "max drawdown unscaled": _drawdown(without_scale),
    }
    return {SCALE_TITLE: per_instrument, CONTRAST_TITLE: contrast}
