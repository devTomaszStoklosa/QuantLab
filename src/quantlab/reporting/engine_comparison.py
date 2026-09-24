from itertools import pairwise

from pydantic import BaseModel

from quantlab.backtest.event_driven.orders import OrderRecord
from quantlab.backtest.run import BacktestRun
from quantlab.core.data.provider import PriceBar
from quantlab.reporting.cost_comparison import RunMetrics, run_metrics


class EngineComparisonRow(BaseModel):
    label: str
    metrics: RunMetrics
    total_costs: float  # as a fraction of the starting capital
    limited_orders: int | None  # None for the vectorized engine, which has no orders


def total_costs(run: BacktestRun) -> float:
    """All costs of a run, as a fraction of its starting capital.

    Snapshot costs are fractions of the previous snapshot's equity, and equity
    starts at 1.0, so each is scaled back by that equity before summing.
    """
    return sum(
        sum(current.costs.values()) * previous.equity
        for previous, current in pairwise(run.snapshots)
    )


def comparison_row(
    label: str,
    run: BacktestRun,
    orders: list[OrderRecord] | None,
    periods_per_year: int,
) -> EngineComparisonRow:
    return EngineComparisonRow(
        label=label,
        metrics=run_metrics(run, periods_per_year),
        total_costs=total_costs(run),
        limited_orders=None if orders is None else sum(order.limited for order in orders),
    )


def max_equity_difference(a: BacktestRun, b: BacktestRun) -> float:
    """Largest absolute gap in normalized equity between two runs of the same dates (REQ-251)."""
    if [snapshot.ts for snapshot in a.snapshots] != [snapshot.ts for snapshot in b.snapshots]:
        raise ValueError("Runs cover different dates")
    return max(
        (abs(x.equity - y.equity) for x, y in zip(a.snapshots, b.snapshots, strict=True)),
        default=0.0,
    )


def capacity(
    orders: list[OrderRecord],
    bars: dict[str, list[PriceBar]],
    capital: float,
    max_participation: float,
) -> float | None:
    """Smallest capital at which an order would exceed the volume limit (REQ-232).

    `orders` come from a run with full fills at `capital`. Its normalized path
    does not depend on the capital, so every order's quantity scales with it,
    and the limit first binds for the order with the largest quantity relative
    to its fill bar's volume. A zero-volume fill bar binds at any capital
    (0.0); a run with no filled order has no capacity to report (None).
    """
    volumes = {
        instrument_id: {bar.ts: bar.volume for bar in instrument_bars}
        for instrument_id, instrument_bars in bars.items()
    }
    filled = [order for order in orders if order.fill_ts is not None]
    if any(order.limited for order in filled):
        raise ValueError("Capacity needs a run with full fills")
    if not filled:
        return None
    usage = max(
        abs(order.quantity) / (max_participation * volume)
        if (volume := volumes[order.instrument_id][order.fill_ts]) > 0
        else float("inf")
        for order in filled
    )
    return capital / usage
