import uuid
from datetime import date
from itertools import pairwise

from pydantic import BaseModel

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.base import Strategy

_ZERO_COST_MODEL_NAME = "zero-cost"


class PortfolioSnapshot(BaseModel):
    ts: date
    cash: float
    positions: dict[str, float]
    equity: float


class BacktestRun(BaseModel):
    id: str
    strategy_name: str
    strategy_params: dict
    cost_model_name: str
    universe_name: str
    start: date
    end: date
    seed: int
    git_sha: str
    snapshots: list[PortfolioSnapshot]


def _trading_dates(bars: dict[str, list[PriceBar]], start: date, end: date) -> list[date]:
    dates = {
        bar.ts
        for instrument_bars in bars.values()
        for bar in instrument_bars
        if start <= bar.ts <= end
    }
    return sorted(dates)


def _closes_by_date(instrument_bars: list[PriceBar]) -> dict[date, float]:
    return {bar.ts: bar.close for bar in instrument_bars}


def run(
    strategy: Strategy,
    bars: dict[str, list[PriceBar]],
    universe_name: str,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
    strategy_name: str,
    strategy_params: dict,
) -> BacktestRun:
    """Vectorized backtest: equal-weight by signal sign, zero transaction cost.

    A signal computed as-of day t decides the position held from t to t+1; that
    position earns the close-to-close return realized over t..t+1 (REQ-010: no
    look-ahead). Equity starts at 1.0 ("growth of $1") and compounds daily.
    Weighting is by sign only, not `signal.strength` - that field is an
    unnormalized per-instrument return (see time_series_momentum.py) and isn't
    comparable across instruments. An instrument missing a bar on either
    endpoint of a period is excluded from that period's weights and return,
    not treated as an error.
    """
    dates = _trading_dates(bars, start, end)
    if not dates:
        raise ValueError(f"No price data available between {start} and {end}")
    closes = {instrument_id: _closes_by_date(instrument_bars) for instrument_id, instrument_bars in bars.items()}

    equity = 1.0
    snapshots = [PortfolioSnapshot(ts=dates[0], cash=equity, positions={}, equity=equity)]

    for previous_date, current_date in pairwise(dates):
        signals = strategy.generate_signals(bars, previous_date)
        active = [
            signal
            for signal in signals
            if signal.direction != "flat"
            and previous_date in closes[signal.instrument_id]
            and current_date in closes[signal.instrument_id]
        ]

        weights: dict[str, float] = {}
        period_return = 0.0
        if active:
            weight_magnitude = 1.0 / len(active)
            for signal in active:
                sign = 1.0 if signal.direction == "long" else -1.0
                weight = sign * weight_magnitude
                weights[signal.instrument_id] = weight
                instrument_closes = closes[signal.instrument_id]
                instrument_return = (
                    instrument_closes[current_date] - instrument_closes[previous_date]
                ) / instrument_closes[previous_date]
                period_return += weight * instrument_return

        equity *= 1.0 + period_return
        invested = sum(abs(weight) for weight in weights.values())
        snapshots.append(
            PortfolioSnapshot(
                ts=current_date,
                cash=equity * (1.0 - invested),
                positions=weights,
                equity=equity,
            )
        )

    return BacktestRun(
        id=str(uuid.uuid4()),
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        cost_model_name=_ZERO_COST_MODEL_NAME,
        universe_name=universe_name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        snapshots=snapshots,
    )
