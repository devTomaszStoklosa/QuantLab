import uuid
from datetime import date

from pydantic import BaseModel

from quantlab.backtest.event_driven.execution import ExecutionModel
from quantlab.backtest.event_driven.feed import BarFeed
from quantlab.backtest.event_driven.fills import FillPolicy, FullFill
from quantlab.backtest.event_driven.orders import OrderRecord
from quantlab.backtest.event_driven.portfolio import Portfolio
from quantlab.backtest.run import BacktestRun, trading_dates
from quantlab.backtest.sizing import equal_weight_by_sign
from quantlab.core.data.provider import PriceBar
from quantlab.costs.base import CostModel
from quantlab.strategy.base import Strategy


class EventDrivenResult(BaseModel):
    run: BacktestRun
    orders: list[OrderRecord]
    execution: str
    capital: float


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
    execution: ExecutionModel,
    fill_policy: FillPolicy | None = None,
    capital: float = 1.0,
) -> EventDrivenResult:
    """Event-driven backtest: one trading date at a time, orders and fills.

    Each date runs the phases of REQ-211 in a fixed order - fills due at the
    open, mark-to-market and snapshot, fills due at the close, then signals and
    new orders - against a feed that has revealed nothing after that date.
    Weights follow the same rule as the vectorized engine, among instruments
    with a bar at the decision close.

    The run ends at the last date's snapshot: no orders are placed then (no
    period is left for them to carry), and orders that could only fill after
    it - next-close orders decided the day before - fall outside the run and
    are not recorded, like any trade after the last close.
    """
    dates = trading_dates(bars, start, end)
    if not dates:
        raise ValueError(f"No price data available between {start} and {end}")
    fills = fill_policy if fill_policy is not None else FullFill()
    feed = BarFeed(bars)
    portfolio = Portfolio(capital, cost_model, feed)

    for ts in dates:
        feed.advance(ts)
        portfolio.apply(execution.due("open", feed, fills))
        portfolio.snapshot(ts)
        if ts == dates[-1]:
            break
        portfolio.apply(execution.due("close", feed, fills))
        signals = strategy.generate_signals(feed.history(), ts)
        tradable = [signal for signal in signals if feed.bar(signal.instrument_id) is not None]
        orders = portfolio.rebalance(equal_weight_by_sign(tradable), ts)
        portfolio.apply(execution.submit(orders, feed, fills))

    return EventDrivenResult(
        run=BacktestRun(
            id=str(uuid.uuid4()),
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            cost_model_name=cost_model.name,
            universe_name=universe_name,
            start=start,
            end=end,
            seed=seed,
            git_sha=git_sha,
            snapshots=portfolio.snapshots,
        ),
        orders=portfolio.records,
        execution=execution.name,
        capital=capital,
    )
