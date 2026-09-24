from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as run_event_driven
from quantlab.backtest.event_driven.execution import CloseExecution, NextBarExecution
from quantlab.backtest.rebalance import Daily, OnSignalChange
from quantlab.backtest.vectorized.engine import run as run_vectorized
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.realistic import RealisticCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.engine_comparison import max_equity_difference
from quantlab.strategy.signal import Signal

_FIRST = date(2024, 1, 1)
_DAYS = 120


def _bars() -> dict[str, list[PriceBar]]:
    rng = np.random.default_rng(3)
    bars = {}
    for instrument_id, drift in (("aaa", 0.002), ("bbb", -0.001), ("ccc", 0.0005)):
        closes = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.02, _DAYS))
        bars[instrument_id] = [
            PriceBar(
                instrument_id=instrument_id,
                ts=_FIRST + timedelta(days=i),
                open=float(close) * 0.998,
                high=float(close) * 1.01,
                low=float(close) * 0.99,
                close=float(close),
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(closes)
        ]
    return bars


class _Constant:
    """Long the same instruments every day."""

    def __init__(self, instruments: tuple[str, ...]) -> None:
        self.instruments = instruments

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        return [
            Signal(instrument_id=i, ts=as_of, direction="long", strength=1.0)
            for i in self.instruments
        ]


class _MonthlyRotation:
    """Long aaa and bbb in odd months, long aaa and short ccc in even ones."""

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        if as_of.month % 2:
            legs = (("aaa", "long"), ("bbb", "long"))
        else:
            legs = (("aaa", "long"), ("ccc", "short"))
        return [Signal(instrument_id=i, ts=as_of, direction=d, strength=1.0) for i, d in legs]


def _vectorized(strategy, cost_model, rebalance, start=_FIRST):
    return run_vectorized(
        strategy=strategy,
        cost_model=cost_model,
        bars=_bars(),
        universe_name="test",
        start=start,
        end=_FIRST + timedelta(days=_DAYS - 1),
        seed=0,
        git_sha="t",
        strategy_name="s",
        strategy_params={},
        rebalance=rebalance,
    )


def _event_driven(strategy, cost_model, rebalance, execution=None, start=_FIRST):
    return run_event_driven(
        strategy=strategy,
        cost_model=cost_model,
        bars=_bars(),
        universe_name="test",
        start=start,
        end=_FIRST + timedelta(days=_DAYS - 1),
        seed=0,
        git_sha="t",
        strategy_name="s",
        strategy_params={},
        execution=execution or CloseExecution(),
        rebalance=rebalance,
    )


def test_daily_never_holds_and_on_signal_change_holds_only_unchanged_targets() -> None:
    targets = {"aaa": 0.5, "bbb": -0.5}

    assert not Daily().holds(targets, dict(targets))
    assert not OnSignalChange().holds(None, targets)
    assert OnSignalChange().holds(targets, dict(targets))
    assert not OnSignalChange().holds(targets, {"aaa": 0.5, "ccc": -0.5})
    assert not OnSignalChange().holds(targets, {"aaa": 1.0})


def test_held_targets_are_buy_and_hold_from_the_first_decision() -> None:
    bars = _bars()
    run = _vectorized(_Constant(("aaa", "bbb")), ZeroCostModel(), OnSignalChange())

    growth = [bars[i][-1].close / bars[i][0].close for i in ("aaa", "bbb")]
    assert run.snapshots[-1].equity == pytest.approx(sum(growth) / 2, rel=1e-12)
    assert [bool(s.traded) for s in run.snapshots[1:]] == [True] + [False] * (_DAYS - 2)


def test_holding_saves_the_cost_of_trading_drift_back() -> None:
    held = _vectorized(_Constant(("aaa", "bbb")), NaiveCostModel(bps=10), OnSignalChange())
    daily = _vectorized(_Constant(("aaa", "bbb")), NaiveCostModel(bps=10), Daily())

    held_costs = sum(sum(s.costs.values()) for s in held.snapshots)
    daily_costs = sum(sum(s.costs.values()) for s in daily.snapshots)
    assert held_costs == pytest.approx(10 / 10_000 * 1.0)  # the first purchase only
    assert daily_costs > 2 * held_costs


def test_positions_drift_with_prices_while_held() -> None:
    run = _vectorized(_Constant(("aaa", "bbb")), ZeroCostModel(), OnSignalChange())

    later = run.snapshots[60].positions
    assert later["aaa"] != pytest.approx(later["bbb"])
    assert sum(later.values()) == pytest.approx(1.0)


def test_both_engines_keep_parity_under_on_signal_change() -> None:
    cost_model = RealisticCostModel(fee_bps=10, k=0.05, vol_window=5)
    start = _FIRST + timedelta(days=10)  # the cost model needs some volatility history
    vectorized = _vectorized(_MonthlyRotation(), cost_model, OnSignalChange(), start=start)
    event_driven = _event_driven(_MonthlyRotation(), cost_model, OnSignalChange(), start=start)

    assert max_equity_difference(vectorized, event_driven.run) < 1e-12
    for v, e in zip(vectorized.snapshots, event_driven.run.snapshots, strict=True):
        assert v.traded.keys() == e.traded.keys()
        for instrument_id, traded in v.traded.items():
            assert e.traded[instrument_id] == pytest.approx(traded, abs=1e-12)
    # Trades happen at the first decision and on the first day of each new month.
    trading_days = [s.ts - timedelta(days=1) for s in vectorized.snapshots if s.traded]
    assert trading_days == [start, date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)]


def test_a_held_event_driven_portfolio_sends_no_orders() -> None:
    result = _event_driven(
        _Constant(("aaa", "bbb")), ZeroCostModel(), OnSignalChange(), NextBarExecution("open")
    )

    assert {record.decision_ts for record in result.orders} == {_FIRST}
