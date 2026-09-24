from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import CloseExecution
from quantlab.backtest.event_driven.orders import OrderRecord
from quantlab.backtest.vectorized.engine import run as vectorized_run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.cost_comparison import run_metrics
from quantlab.risk.conditional import regime_conditional_metrics
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.validation.walk_forward import WalkForwardValidator

_START = date(2026, 1, 1)


def _day(offset: int) -> date:
    return _START + timedelta(days=offset)


def _bar(instrument_id: str, day: int, close: float, volume: float = 1.0) -> PriceBar:
    return PriceBar(
        instrument_id=instrument_id,
        ts=_day(day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        source="test",
    )


class _FixedSignals:
    def __init__(self, signals_by_day: dict[int, list[tuple[str, str]]]) -> None:
        self._signals_by_day = signals_by_day

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        return [
            Signal(instrument_id=instrument_id, ts=as_of, direction=direction, strength=0.0)
            for instrument_id, direction in self._signals_by_day.get((as_of - _START).days, [])
        ]


def _run(strategy, bars, days: int, cost_model=None, capital: float = 1.0):
    return event_driven_run(
        strategy=strategy,
        cost_model=cost_model or ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=_START,
        end=_day(days - 1),
        seed=0,
        git_sha="test",
        strategy_name="test",
        strategy_params={},
        execution=CloseExecution(),
        capital=capital,
    )


def test_close_execution_fills_every_order_at_the_decision_close() -> None:
    bars = {"a": [_bar("a", day, close) for day, close in enumerate([100.0, 110.0, 99.0])]}
    strategy = _FixedSignals({0: [("a", "long")], 1: [("a", "short")]})

    result = _run(strategy, bars, days=3, capital=1_000.0)

    assert [(order.decision_ts, order.fill_ts, order.fill_price) for order in result.orders] == [
        (_day(0), _day(0), 100.0),
        (_day(1), _day(1), 110.0),
    ]
    assert result.orders[0].quantity == pytest.approx(10.0)  # 1 000 / 100
    # Flip from long 10 to short: equity 1 100 at the close of day 1, target -10.
    assert result.orders[1].quantity == pytest.approx(-20.0)
    assert [snapshot.equity for snapshot in result.run.snapshots] == pytest.approx(
        [1.0, 1.1, 1.1 * (1.0 + 0.1)]
    )
    assert result.execution == "close"


def test_no_orders_are_placed_on_the_last_date() -> None:
    bars = {"a": [_bar("a", day, 100.0) for day in range(3)]}
    strategy = _FixedSignals({day: [("a", "long")] for day in range(3)})

    result = _run(strategy, bars, days=3)

    assert {order.decision_ts for order in result.orders} == {_day(0)}


def test_a_run_without_signals_stays_in_cash() -> None:
    bars = {"a": [_bar("a", day, 100.0 + day) for day in range(4)]}

    result = _run(_FixedSignals({}), bars, days=4)

    assert [snapshot.equity for snapshot in result.run.snapshots] == [1.0] * 4
    assert all(snapshot.positions == {} for snapshot in result.run.snapshots)
    assert result.orders == []


def test_order_costs_add_up_to_the_snapshot_costs() -> None:
    bars = {
        "a": [_bar("a", day, close) for day, close in enumerate([100.0, 105.0, 95.0, 101.0])],
        "b": [_bar("b", day, close) for day, close in enumerate([50.0, 49.0, 52.0, 51.0])],
    }
    strategy = _FixedSignals(
        {0: [("a", "long"), ("b", "short")], 1: [("a", "long")], 2: [("b", "long")]}
    )

    result = _run(strategy, bars, days=4, cost_model=NaiveCostModel(bps=25), capital=10_000.0)

    snapshots = result.run.snapshots
    snapshot_costs = sum(
        sum(current.costs.values()) * previous.equity for previous, current in pairwise(snapshots)
    )
    assert sum(order.cost for order in result.orders) / 10_000.0 == pytest.approx(snapshot_costs)
    assert snapshot_costs > 0


def test_an_instrument_without_a_bar_on_the_fill_date_keeps_its_position() -> None:
    # "a" has no bar on day 2: the exit decided that day cannot fill, the
    # position stays and is valued at its last close until "a" trades again.
    bars = {
        "a": [_bar("a", 0, 100.0), _bar("a", 1, 110.0), _bar("a", 3, 120.0), _bar("a", 4, 90.0)],
        "b": [_bar("b", day, 10.0) for day in range(5)],
    }
    strategy = _FixedSignals({0: [("a", "long")], 1: [("a", "long")]})

    result = _run(strategy, bars, days=5)

    cancelled = [order for order in result.orders if order.filled_quantity == 0.0]
    assert [(order.instrument_id, order.decision_ts) for order in cancelled] == [("a", _day(2))]
    equity = [snapshot.equity for snapshot in result.run.snapshots]
    assert equity == pytest.approx([1.0, 1.1, 1.1, 1.2, 1.2])  # closed at day 3's close
    assert result.run.snapshots[3].positions == {"a": pytest.approx(1.0)}
    assert result.run.snapshots[4].positions == {}


def test_equity_based_consumers_accept_an_event_driven_run() -> None:
    # AC-6: metrics, walk-forward and regime metrics read only the contract.
    rng = np.random.default_rng(2)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.03, 900))
    bars = {"a": [_bar("a", day, float(close)) for day, close in enumerate(closes)]}
    args = {
        "strategy": TimeSeriesMomentum(lookback_days=30),
        "cost_model": NaiveCostModel(bps=10),
        "bars": bars,
        "universe_name": "test",
        "start": _day(31),
        "end": _day(899),
        "seed": 0,
        "git_sha": "test",
        "strategy_name": "momentum",
        "strategy_params": {},
    }
    vectorized = vectorized_run(**args)
    event_driven = event_driven_run(**args, execution=CloseExecution(), capital=50_000.0).run
    labels = {
        snapshot.ts: "low" if snapshot.ts.month < 7 else "high" for snapshot in vectorized.snapshots
    }

    assert run_metrics(event_driven, 365).model_dump() == pytest.approx(
        run_metrics(vectorized, 365).model_dump(), rel=1e-9
    )
    walk_forward = WalkForwardValidator(periods_per_year=365)
    assert walk_forward.validate(event_driven).passed == walk_forward.validate(vectorized).passed
    by_regime = regime_conditional_metrics(event_driven, labels, 365)
    assert {label: metrics.sharpe for label, metrics in by_regime.items()} == pytest.approx(
        {
            label: metrics.sharpe
            for label, metrics in regime_conditional_metrics(vectorized, labels, 365).items()
        },
        rel=1e-9,
    )


def test_empty_date_range_is_rejected() -> None:
    bars = {"a": [_bar("a", 0, 100.0)]}

    with pytest.raises(ValueError, match="No price data"):
        event_driven_run(
            strategy=_FixedSignals({}),
            cost_model=ZeroCostModel(),
            bars=bars,
            universe_name="test",
            start=_day(10),
            end=_day(20),
            seed=0,
            git_sha="test",
            strategy_name="test",
            strategy_params={},
            execution=CloseExecution(),
        )


def _record(**overrides) -> dict:
    fields = {
        "instrument_id": "a",
        "decision_ts": _day(0),
        "quantity": 2.0,
        "decision_equity": 100.0,
        "filled_quantity": 2.0,
        "fill_ts": _day(0),
        "fill_price": 50.0,
        "cost": 0.1,
    }
    return fields | overrides


@pytest.mark.parametrize(
    "overrides",
    [
        {"quantity": 0.0, "filled_quantity": 0.0, "fill_ts": None, "fill_price": None},
        {"filled_quantity": -1.0},
        {"filled_quantity": 3.0},
        {"fill_ts": _day(-1)},
        {"fill_price": None},
        {"filled_quantity": 0.0},
        {"cost": -0.1},
    ],
)
def test_order_record_rejects_inconsistent_outcomes(overrides: dict) -> None:
    with pytest.raises(ValueError):
        OrderRecord(**_record(**overrides))


def test_order_record_marks_partial_and_cancelled_orders_as_limited() -> None:
    assert not OrderRecord(**_record()).limited
    assert OrderRecord(**_record(filled_quantity=1.0)).limited
    assert OrderRecord(
        **_record(filled_quantity=0.0, fill_ts=None, fill_price=None, cost=0.0)
    ).limited
