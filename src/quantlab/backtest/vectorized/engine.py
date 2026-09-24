import uuid
from datetime import date
from itertools import pairwise

from pydantic import BaseModel, Field

from quantlab.core.data.provider import PriceBar
from quantlab.costs.base import CostModel
from quantlab.strategy.base import Strategy


class PortfolioSnapshot(BaseModel):
    ts: date
    cash: float
    positions: dict[str, float]
    equity: float
    # Cost charged per instrument in the period ending at ts, as a fraction of
    # the previous snapshot's equity; includes instruments being closed.
    costs: dict[str, float] = Field(default_factory=dict)


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
    cost_model: CostModel,
    bars: dict[str, list[PriceBar]],
    universe_name: str,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
    strategy_name: str,
    strategy_params: dict,
) -> BacktestRun:
    """Vectorized backtest: equal-weight by signal sign, daily rebalancing.

    A signal computed as-of day t decides the position held from t to t+1; that
    position earns the close-to-close return realized over t..t+1 (REQ-010: no
    look-ahead). Equity starts at 1.0 ("growth of $1") and compounds daily.
    Weighting is by sign only, not `signal.strength` - that field is an
    unnormalized per-instrument return (see time_series_momentum.py) and isn't
    comparable across instruments. An instrument missing a bar on either
    endpoint of a period is excluded from that period's weights and return,
    not treated as an error.

    Rebalancing happens at the close of t and its cost is charged in the same
    period. Turnover is measured against the weights actually held after the
    previous period's price moves, not the previous targets: prices push the
    portfolio off equal weight every day, and trading it back is real trading.
    """
    dates = _trading_dates(bars, start, end)
    if not dates:
        raise ValueError(f"No price data available between {start} and {end}")
    closes = {instrument_id: _closes_by_date(instrument_bars) for instrument_id, instrument_bars in bars.items()}

    equity = 1.0
    snapshots = [PortfolioSnapshot(ts=dates[0], cash=equity, positions={}, equity=equity)]
    held: dict[str, float] = {}

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
        instrument_returns: dict[str, float] = {}
        if active:
            weight_magnitude = 1.0 / len(active)
            for signal in active:
                sign = 1.0 if signal.direction == "long" else -1.0
                weights[signal.instrument_id] = sign * weight_magnitude
                instrument_closes = closes[signal.instrument_id]
                instrument_returns[signal.instrument_id] = (
                    instrument_closes[current_date] - instrument_closes[previous_date]
                ) / instrument_closes[previous_date]

        instrument_costs: dict[str, float] = {}
        for instrument_id in held.keys() | weights.keys():
            traded_weight = abs(weights.get(instrument_id, 0.0) - held.get(instrument_id, 0.0))
            if traded_weight > 0.0:
                instrument_costs[instrument_id] = cost_model.cost(
                    bars[instrument_id], previous_date, traded_weight
                )
        total_cost = sum(instrument_costs.values())

        gross_return = sum(
            weight * instrument_returns[instrument_id] for instrument_id, weight in weights.items()
        )
        period_return = gross_return - total_cost

        equity *= 1.0 + period_return
        held = {
            instrument_id: weight * (1.0 + instrument_returns[instrument_id]) / (1.0 + period_return)
            for instrument_id, weight in weights.items()
        }
        invested = sum(abs(weight) for weight in weights.values())
        snapshots.append(
            PortfolioSnapshot(
                ts=current_date,
                cash=equity * (1.0 - invested),
                positions=weights,
                equity=equity,
                costs=instrument_costs,
            )
        )

    return BacktestRun(
        id=str(uuid.uuid4()),
        strategy_name=strategy_name,
        strategy_params=strategy_params,
        cost_model_name=cost_model.name,
        universe_name=universe_name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        snapshots=snapshots,
    )
