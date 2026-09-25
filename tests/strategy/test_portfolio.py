from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as run_event_driven
from quantlab.backtest.event_driven.execution import CloseExecution
from quantlab.backtest.event_driven.fills import FullFill
from quantlab.backtest.rebalance import Daily
from quantlab.backtest.sizing import CarriedWeights, EqualWeightBySign, PairWeights
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar
from quantlab.costs.realistic import RealisticCostModel
from quantlab.portfolio.allocation import EqualWeight, InverseVolatility, eligible_sleeves
from quantlab.reporting.engine_comparison import max_equity_difference
from quantlab.strategy.portfolio import Sleeve, SleeveHistory, StrategyPortfolio
from quantlab.strategy.selected_parameter import net_returns
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

_FIRST = date(2017, 1, 1)
_LAST = date(2019, 12, 31)
_START = date(2018, 1, 1)
_ANCHOR = date(2017, 4, 1)


def _costs() -> RealisticCostModel:
    return RealisticCostModel(fee_bps=10, k=0.05, vol_window=30)


def _bars() -> dict[str, list[PriceBar]]:
    """Two instruments with trends that turn every 90 days, and noise."""
    rng = np.random.default_rng(42)
    days = (_LAST - _FIRST).days + 1
    drift = np.repeat(rng.choice([-0.003, 0.003], size=days // 90 + 1), 90)[:days]
    bars = {}
    for instrument_id in ("aaa", "bbb"):
        closes = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.02, days))
        bars[instrument_id] = [
            PriceBar(
                instrument_id=instrument_id,
                ts=_FIRST + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(closes)
        ]
    return bars


def _sleeve(name: str, build) -> Sleeve:
    return Sleeve(name, build, EqualWeightBySign(), Daily(), _costs())


def _momentum_and_reversal() -> list[Sleeve]:
    return [
        _sleeve("momentum", lambda: TimeSeriesMomentum(60)),
        _sleeve("reversal", lambda: ShortTermReversal(7)),
    ]


def _portfolio(sleeves: list[Sleeve], rule=None, window: int = 90, min_days: int = 60):
    return StrategyPortfolio(
        SleeveHistory(sleeves, _ANCHOR), rule or InverseVolatility(), window, min_days
    )


def _run(strategy, bars, start: date = _START, end: date = _LAST, sizer=None):
    return run_backtest(
        strategy=strategy,
        cost_model=_costs(),
        bars=bars,
        universe_name="u",
        start=start,
        end=end,
        seed=0,
        git_sha="x",
        strategy_name="x",
        strategy_params={},
        sizer=sizer if sizer is not None else CarriedWeights(),
    )


def _signal(instrument_id: str, direction: str, weight: float | None) -> Signal:
    return Signal(
        instrument_id=instrument_id,
        ts=_START,
        direction=direction,
        strength=1.0,
        weight=weight,
    )


def test_carried_weights_keep_the_signed_weights_of_the_signals() -> None:
    signals = [
        _signal("aaa", "long", 0.3),
        _signal("bbb", "short", 0.25),
        _signal("ccc", "flat", None),
    ]

    assert CarriedWeights().weights(signals) == {"aaa": 0.3, "bbb": -0.25}
    with pytest.raises(ValueError, match="must carry a weight"):
        CarriedWeights().weights([_signal("aaa", "long", None)])


def test_the_weights_are_the_rule_applied_to_the_sleeves_standalone_returns() -> None:
    bars = _bars()
    sleeves = _momentum_and_reversal()
    portfolio = _portfolio(sleeves)

    record = portfolio.allocation(bars, date(2018, 6, 1))

    known = {i: [bar for bar in series if bar.ts < date(2018, 6, 1)] for i, series in bars.items()}
    history = np.column_stack(
        [
            net_returns(sleeve.build(), _costs(), known, _ANCHOR, date(2018, 5, 31))
            for sleeve in sleeves
        ]
    )
    expected = InverseVolatility().weights(history[-90:], eligible_sleeves(history, 90, 60))
    assert list(record.weights.values()) == pytest.approx(expected.tolist(), rel=1e-12)
    assert record.history_days == len(history)
    assert sum(record.weights.values()) == pytest.approx(1.0)
    assert record.diversification_ratio > 1.0  # momentum and reversal move apart


def test_bars_on_or_after_the_rebalance_day_do_not_change_its_weights() -> None:
    bars = _bars()
    future = {
        instrument_id: [
            replace(bar, close=bar.close * (3.0 if bar.ts >= date(2018, 6, 1) else 1.0))
            for bar in series
        ]
        for instrument_id, series in bars.items()
    }
    month = date(2018, 6, 1)

    changed = _portfolio(_momentum_and_reversal()).allocation(future, month)

    assert changed == _portfolio(_momentum_and_reversal()).allocation(bars, month)


def test_no_position_before_a_sleeve_is_eligible() -> None:
    bars = _bars()
    # Anchored at the run's start: 60 days of history come only in March.
    portfolio = StrategyPortfolio(
        SleeveHistory(_momentum_and_reversal(), _START), InverseVolatility(), 90, 60
    )

    run = _run(portfolio, bars, end=date(2018, 4, 30))

    held = [snapshot.ts for snapshot in run.snapshots if snapshot.positions]
    assert held[0] >= date(2018, 3, 2)
    assert portfolio.allocations[0].weights == {"momentum": 0.0, "reversal": 0.0}


def test_a_portfolio_of_one_sleeve_is_that_sleeve() -> None:
    bars = _bars()
    sleeve = _sleeve("momentum", lambda: TimeSeriesMomentum(60))
    portfolio = _portfolio([sleeve], rule=EqualWeight())

    combined = _run(portfolio, bars)
    alone = _run(TimeSeriesMomentum(60), bars, sizer=EqualWeightBySign())

    assert {record.weights["momentum"] for record in portfolio.allocations} == {1.0}
    assert [s.equity for s in combined.snapshots] == pytest.approx(
        [s.equity for s in alone.snapshots], rel=1e-12
    )


class _Always:
    def __init__(self, direction: str) -> None:
        self.direction = direction

    def generate_signals(self, bars, as_of):
        return [Signal(instrument_id="aaa", ts=as_of, direction=self.direction, strength=1.0)]


def test_opposite_sleeves_net_out_and_trade_nothing() -> None:
    bars = _bars()
    sleeves = [
        _sleeve("long", lambda: _Always("long")),
        _sleeve("short", lambda: _Always("short")),
    ]
    portfolio = _portfolio(sleeves, rule=EqualWeight())

    run = _run(portfolio, bars)

    # Each sleeve alone pays to trade; together they hold nothing and pay nothing.
    assert all(record.weights == {"long": 0.5, "short": 0.5} for record in portfolio.allocations)
    assert {snapshot.equity for snapshot in run.snapshots} == {1.0}
    assert not any(snapshot.traded for snapshot in run.snapshots)
    alone = net_returns(_Always("long"), _costs(), bars, _START, _LAST)
    assert alone[0] != 0.0


def test_both_engines_trade_the_portfolio_alike() -> None:
    bars = _bars()
    sleeves = [
        *_momentum_and_reversal(),
        Sleeve("pair", lambda: _PairLegs(), PairWeights(), Daily(), _costs()),
    ]

    vectorized = _run(_portfolio(sleeves), bars)
    event_driven = run_event_driven(
        strategy=_portfolio(sleeves),
        cost_model=_costs(),
        bars=bars,
        universe_name="u",
        start=_START,
        end=_LAST,
        seed=0,
        git_sha="x",
        strategy_name="x",
        strategy_params={},
        execution=CloseExecution(),
        fill_policy=FullFill(),
        capital=1e6,
        sizer=CarriedWeights(),
    )

    assert any(snapshot.traded for snapshot in vectorized.snapshots)
    assert max_equity_difference(vectorized, event_driven.run) < 1e-9


class _PairLegs:
    """Long aaa and short bbb with fixed weights while aaa is below its 30-day mean."""

    def generate_signals(self, bars, as_of):
        history = [bar.close for bar in bars["aaa"] if bar.ts <= as_of][-30:]
        if len(history) < 30 or history[-1] >= np.mean(history):
            return []
        return [
            Signal(instrument_id="aaa", ts=as_of, direction="long", strength=1.0, weight=0.6),
            Signal(instrument_id="bbb", ts=as_of, direction="short", strength=1.0, weight=0.4),
        ]


def test_sleeve_history_is_the_prefix_of_one_continuous_run() -> None:
    bars = _bars()
    sleeves = _momentum_and_reversal()
    history = SleeveHistory(sleeves, _ANCHOR)

    returns = history.returns(bars, date(2019, 3, 1))

    full = np.column_stack(
        [net_returns(sleeve.build(), _costs(), bars, _ANCHOR, _LAST) for sleeve in sleeves]
    )
    assert returns == pytest.approx(full[: len(returns)], rel=1e-12, abs=1e-15)
    assert len(returns) == (date(2019, 2, 28) - _ANCHOR).days


def test_portfolios_with_different_rules_can_share_the_sleeve_history() -> None:
    bars = _bars()
    history = SleeveHistory(_momentum_and_reversal(), _ANCHOR)
    equal = StrategyPortfolio(history, EqualWeight(), 90, 60)
    inverse = StrategyPortfolio(history, InverseVolatility(), 90, 60)

    first = equal.allocation(bars, date(2018, 6, 1))
    second = inverse.allocation(bars, date(2018, 6, 1))

    assert first.weights == {"momentum": 0.5, "reversal": 0.5}
    assert second.weights != first.weights
    assert len(history._returns) == 1  # computed once


def test_the_sleeve_history_is_remembered_by_the_bars_not_only_the_day() -> None:
    bars = _bars()
    stressed = {
        instrument_id: [replace(bar, close=bar.close * 0.5) for bar in series]
        for instrument_id, series in bars.items()
    }
    history = SleeveHistory(_momentum_and_reversal(), _ANCHOR)
    refetched = {instrument_id: list(series) for instrument_id, series in bars.items()}

    first = history.returns(bars, date(2018, 6, 1))
    again = history.returns(refetched, date(2018, 6, 1))  # equal bars, other objects
    other = history.returns(stressed, date(2018, 6, 1))

    assert again is first
    assert other is not first
    assert len(history._returns) == 2


def test_net_positions_are_the_weighted_sum_of_the_sleeves_targets() -> None:
    bars = _bars()
    sleeves = _momentum_and_reversal()
    portfolio = _portfolio(sleeves)
    as_of = date(2018, 7, 15)

    signals = portfolio.generate_signals(bars, as_of)

    weights = portfolio.allocation(bars, date(2018, 7, 1)).weights
    expected: dict[str, float] = {}
    for sleeve in sleeves:
        for instrument_id, target in (
            EqualWeightBySign().weights(sleeve.build().generate_signals(bars, as_of)).items()
        ):
            expected[instrument_id] = expected.get(instrument_id, 0.0) + (
                weights[sleeve.name] * target
            )
    assert CarriedWeights().weights(signals) == pytest.approx(
        {i: w for i, w in expected.items() if w != 0.0}
    )
