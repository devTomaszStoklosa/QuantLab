import uuid
from datetime import date
from itertools import pairwise

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot, trading_dates
from quantlab.backtest.sizing import EqualWeightBySign, Sizer
from quantlab.core.data.provider import PriceBar
from quantlab.costs.base import CostModel
from quantlab.strategy.base import Strategy


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
    sizer: Sizer | None = None,
) -> BacktestRun:
    """Vectorized backtest: daily rebalancing to the sizer's weights.

    A signal computed as-of day t decides the position held from t to t+1; that
    position earns the close-to-close return realized over t..t+1 (REQ-010: no
    look-ahead). Equity starts at 1.0 ("growth of $1") and compounds daily.
    Weights come from `sizer` (equal weight by sign unless the hypothesis
    chooses another), shared with the event-driven engine. An instrument
    missing a bar on either
    endpoint of a period is excluded from that period's weights and return,
    not treated as an error.

    A delisting bar (q5) ends an instrument: the period into it earns the
    delisting return, and the position then turns into cash at that value -
    no trade, so no cost and no turnover (REQ-523).

    Rebalancing happens at the close of t and its cost is charged in the same
    period. Turnover is measured against the weights actually held after the
    previous period's price moves, not the previous targets: prices push the
    portfolio off equal weight every day, and trading it back is real trading.
    """
    sizer = sizer if sizer is not None else EqualWeightBySign()
    dates = trading_dates(bars, start, end)
    if not dates:
        raise ValueError(f"No price data available between {start} and {end}")
    closes = {instrument_id: _closes_by_date(instrument_bars) for instrument_id, instrument_bars in bars.items()}
    delisted_on = {
        instrument_id: {bar.ts for bar in instrument_bars if bar.delisting}
        for instrument_id, instrument_bars in bars.items()
    }

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

        weights = sizer.weights(active)
        instrument_returns = {
            instrument_id: (
                closes[instrument_id][current_date] - closes[instrument_id][previous_date]
            )
            / closes[instrument_id][previous_date]
            for instrument_id in weights
        }

        instrument_costs: dict[str, float] = {}
        instrument_traded: dict[str, float] = {}
        # Sorted, so the cost sum has the same order in every process (set order
        # depends on string hashing, randomized per interpreter).
        for instrument_id in sorted(held.keys() | weights.keys()):
            if previous_date in delisted_on[instrument_id]:
                continue  # cashed out at its delisting value, not traded
            traded_weight = abs(weights.get(instrument_id, 0.0) - held.get(instrument_id, 0.0))
            if traded_weight > 0.0:
                instrument_traded[instrument_id] = traded_weight
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
                traded=instrument_traded,
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
