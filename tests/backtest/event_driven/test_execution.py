"""AC-3: execution on the next bar, against results worked out by hand."""

from datetime import date, timedelta

import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import CloseExecution, NextBarExecution
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.signal import Signal

_START = date(2026, 1, 1)


def _day(offset: int) -> date:
    return _START + timedelta(days=offset)


def _bar(instrument_id: str, day: int, open_: float, close: float) -> PriceBar:
    return PriceBar(
        instrument_id=instrument_id,
        ts=_day(day),
        open=open_,
        high=max(open_, close),
        low=min(open_, close),
        close=close,
        volume=1.0,
        source="test",
    )


# (open, close) per day: the open differs from the previous close, so the
# three execution modes give three different runs.
_PRICES = [(100.0, 100.0), (102.0, 110.0), (108.0, 99.0), (99.0, 99.0), (99.0, 95.0)]
_BARS = {"a": [_bar("a", day, open_, close) for day, (open_, close) in enumerate(_PRICES)]}


class _LongForTwoDays:
    """Long on days 0 and 1, then flat."""

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        direction = "long" if as_of <= _day(1) else "flat"
        return [Signal(instrument_id="a", ts=as_of, direction=direction, strength=0.0)]


def _run(execution, cost_model=None, bars=None):
    return event_driven_run(
        strategy=_LongForTwoDays(),
        cost_model=cost_model or ZeroCostModel(),
        bars=bars or _BARS,
        universe_name="test",
        start=_day(0),
        end=_day(4),
        seed=0,
        git_sha="test",
        strategy_name="test",
        strategy_params={},
        execution=execution,
        capital=1_000.0,
    )


def test_close_execution_trades_at_the_signal_close() -> None:
    result = _run(CloseExecution())

    # Buy 10 at 100, hold to 110, re-target at 110 (no trade), exit at 99.
    assert [s.equity for s in result.run.snapshots] == pytest.approx([1.0, 1.1, 0.99, 0.99, 0.99])


def test_next_open_execution_fills_at_the_following_open() -> None:
    result = _run(NextBarExecution("open"))

    # Day 0: order +10 (1 000 / close 100). Day 1 open: filled at 102, cash -20;
    # close 110 -> equity 1 080. Re-target 1 080 / 110 = 9.8182, order -0.1818.
    # Day 2 open: sold at 108, cash -0.3636; close 99 -> 971.64. Exit decided
    # at day 2's close fills at day 3's open, 99: all cash, 971.64.
    held = 1_080.0 / 110.0
    cash = -20.0 + (10.0 - held) * 108.0
    after_day_2 = cash + held * 99.0
    assert [s.equity for s in result.run.snapshots] == pytest.approx(
        [1.0, 1.08, after_day_2 / 1_000.0, after_day_2 / 1_000.0, after_day_2 / 1_000.0]
    )
    assert [(o.decision_ts, o.fill_ts, o.fill_price) for o in result.orders] == [
        (_day(0), _day(1), 102.0),
        (_day(1), _day(2), 108.0),
        (_day(2), _day(3), 99.0),
    ]
    # Positions are the filled quantities at the decision close's prices and
    # equity: the order was sized for weight 1, so it reads as weight 1.
    assert [s.positions for s in result.run.snapshots] == [
        {},
        {"a": pytest.approx(1.0)},
        {"a": pytest.approx(1.0)},
        {},
        {},
    ]
    assert result.run.snapshots[1].traded == {"a": pytest.approx(1.02)}
    assert result.execution == "next-open"


def test_next_close_execution_is_a_full_day_late() -> None:
    result = _run(NextBarExecution("close"))

    # Day 0: order +10 at 100 fills at day 1's close, 110: cash -100, equity
    # still 1 000 at day 1 (bought at the close). Re-target at day 1's close:
    # 1 000 / 110 = 9.0909, order -0.9091, filled at day 2's close, 99.
    # Day 2 marks 10 at 99: 890. Exit decided on day 2 fills at day 3's close.
    assert [s.equity for s in result.run.snapshots] == pytest.approx([1.0, 1.0, 0.89, 0.89, 0.89])
    assert [(o.decision_ts, o.fill_ts, o.fill_price) for o in result.orders] == [
        (_day(0), _day(1), 110.0),
        (_day(1), _day(2), 99.0),
        (_day(2), _day(3), 99.0),
    ]
    # Day 2 carried 10 units bought for weight 1 at 100 but filled at 110:
    # 10 * 110 / 1 000 = 1.1 of the decision equity.
    assert result.run.snapshots[2].positions == {"a": pytest.approx(1.1)}
    assert result.run.snapshots[1].positions == {}


def test_every_next_bar_fill_comes_after_its_decision() -> None:
    for phase in ("open", "close"):
        result = _run(NextBarExecution(phase))

        assert all(order.fill_ts > order.decision_ts for order in result.orders)


def test_costs_are_charged_on_the_filled_weight_at_the_decision_equity() -> None:
    result = _run(NextBarExecution("open"), cost_model=NaiveCostModel(bps=10))

    first = result.orders[0]
    # 10 units filled at 102 against a decision equity of 1 000: weight 1.02.
    assert first.cost == pytest.approx(0.001 * 1.02 * 1_000.0)
    assert result.run.snapshots[1].costs == {"a": pytest.approx(0.001 * 1.02)}
    assert result.run.snapshots[1].equity == pytest.approx((1_080.0 - first.cost) / 1_000.0)


def test_an_order_with_no_bar_on_the_next_date_is_cancelled() -> None:
    # "a" skips day 1; "b" keeps the calendar going.
    bars = {
        "a": [
            _bar("a", day, open_, close) for day, (open_, close) in enumerate(_PRICES) if day != 1
        ],
        "b": [_bar("b", day, 10.0, 10.0) for day in range(5)],
    }

    result = _run(NextBarExecution("open"), bars=bars)

    first = result.orders[0]
    assert (first.decision_ts, first.filled_quantity, first.fill_ts) == (_day(0), 0.0, None)
    assert first.limited
    assert result.run.snapshots[1].equity == 1.0


def test_orders_that_would_fill_after_the_last_snapshot_are_outside_the_run() -> None:
    bars = {"a": _BARS["a"][:3]}  # days 0-2; the day-1 re-target would fill at day 2's close

    result = event_driven_run(
        strategy=_LongForTwoDays(),
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=_day(0),
        end=_day(2),
        seed=0,
        git_sha="test",
        strategy_name="test",
        strategy_params={},
        execution=NextBarExecution("close"),
        capital=1_000.0,
    )

    assert [o.decision_ts for o in result.orders] == [_day(0)]
    assert result.run.snapshots[-1].ts == _day(2)
