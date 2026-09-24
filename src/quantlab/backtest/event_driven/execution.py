from collections.abc import Callable
from typing import Literal, Protocol

from quantlab.backtest.event_driven.feed import BarFeed
from quantlab.backtest.event_driven.fills import FillPolicy
from quantlab.backtest.event_driven.orders import Execution, Order
from quantlab.core.data.provider import PriceBar

Phase = Literal["open", "close"]


class ExecutionModel(Protocol):
    """When and at what price orders fill (REQ-220, REQ-221, REQ-223).

    `submit` receives the orders created at a decision close and returns those
    it fills right away; any it keeps are returned by `due` in a later phase.
    Fills use only the feed's current bar, so no fill can come from the future.
    """

    name: str

    def submit(self, orders: list[Order], feed: BarFeed, fills: FillPolicy) -> list[Execution]: ...

    def due(self, phase: Phase, feed: BarFeed, fills: FillPolicy) -> list[Execution]: ...


def execute(
    order: Order, feed: BarFeed, fills: FillPolicy, price: Callable[[PriceBar], float]
) -> Execution:
    """Fill an order on the feed's current bar, or cancel it if there is none."""
    bar = feed.bar(order.instrument_id)
    if bar is None:
        return Execution.cancelled(order)
    filled = fills.fillable(order.quantity, bar)
    if filled == 0.0:
        return Execution.cancelled(order)
    return Execution(order=order, filled_quantity=filled, fill_ts=bar.ts, fill_price=price(bar))


def _close(bar: PriceBar) -> float:
    return bar.close


class CloseExecution:
    """Fill at the close the signal was computed from - the vectorized engine's
    assumption, kept for parity (REQ-220)."""

    name = "close"

    def submit(self, orders: list[Order], feed: BarFeed, fills: FillPolicy) -> list[Execution]:
        return [execute(order, feed, fills, _close) for order in orders]

    def due(self, phase: Phase, feed: BarFeed, fills: FillPolicy) -> list[Execution]:
        return []


_PRICE_AT: dict[Phase, Callable[[PriceBar], float]] = {
    "open": lambda bar: bar.open,
    "close": _close,
}


class NextBarExecution:
    """Fill at the open or the close of the next trading date (REQ-221).

    Orders decided at the close of t wait until the loop reaches the next date
    and fill at that bar's `phase` price; an instrument with no bar that day
    has its order cancelled. The open is the first price available once the
    signal is known; the close is a full day late, which shows how fast the
    signal loses its value.
    """

    def __init__(self, phase: Phase) -> None:
        self.phase = phase
        self.name = f"next-{phase}"
        self._price = _PRICE_AT[phase]
        self._pending: list[Order] = []

    def submit(self, orders: list[Order], feed: BarFeed, fills: FillPolicy) -> list[Execution]:
        if self._pending:
            raise RuntimeError("New orders submitted while earlier ones are still pending")
        self._pending = list(orders)
        return []

    def due(self, phase: Phase, feed: BarFeed, fills: FillPolicy) -> list[Execution]:
        if phase != self.phase:
            return []
        executions = [execute(order, feed, fills, self._price) for order in self._pending]
        self._pending = []
        return executions
