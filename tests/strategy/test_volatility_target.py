import math
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as run_event_driven
from quantlab.backtest.event_driven.execution import CloseExecution
from quantlab.backtest.event_driven.fills import FullFill
from quantlab.backtest.sizing import EqualWeightBySign, ScaledEqualWeight
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar
from quantlab.costs.realistic import RealisticCostModel
from quantlab.reporting.engine_comparison import max_equity_difference
from quantlab.risk.volatility import RollingVolatility
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.strategy.volatility_target import VolatilityTargeted

_FIRST = date(2017, 1, 1)
_LAST = date(2019, 12, 31)
_START = date(2018, 1, 1)


def _series(instrument_id: str, returns: np.ndarray) -> list[PriceBar]:
    closes = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + returns]))
    return [
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


def _bars() -> dict[str, list[PriceBar]]:
    """Two instruments whose trends turn every 90 days and whose volatility changes
    every 120 days, so the scale moves and sometimes reaches the cap."""
    rng = np.random.default_rng(11)
    days = (_LAST - _FIRST).days
    drift = np.repeat(rng.choice([-0.003, 0.003], size=days // 90 + 1), 90)[:days]
    volatility = np.repeat(np.resize([0.01, 0.06, 0.03], days // 120 + 1), 120)[:days]
    return {
        instrument_id: _series(instrument_id, drift + volatility * rng.normal(0.0, 1.0, days))
        for instrument_id in ("aaa", "bbb")
    }


def _costs() -> RealisticCostModel:
    return RealisticCostModel(fee_bps=10, k=0.05, vol_window=30)


def _scaled(target: float = 0.4, max_scale: float = 1.0, window: int = 30) -> VolatilityTargeted:
    return VolatilityTargeted(
        inner=TimeSeriesMomentum(lookback_days=60),
        estimator=RollingVolatility(window_days=window),
        target_volatility=target,
        max_scale=max_scale,
        periods_per_year=365,
    )


def _run(strategy, sizer, bars):
    return run_backtest(
        strategy=strategy,
        cost_model=_costs(),
        bars=bars,
        universe_name="u",
        start=_START,
        end=_LAST,
        seed=0,
        git_sha="x",
        strategy_name="x",
        strategy_params={},
        sizer=sizer,
    )


def test_the_scale_is_the_target_over_the_annualized_estimate() -> None:
    x = 0.04
    bars = {"aaa": _series("aaa", np.array([x if i % 2 == 0 else -x for i in range(100)]))}
    day = _FIRST + timedelta(days=100)
    strategy = _scaled(target=0.4, window=30)

    sigma = x * math.sqrt(30 / 29)  # alternating returns, known upfront
    assert strategy.scale(bars["aaa"], day) == pytest.approx(0.4 / (sigma * math.sqrt(365)))
    # 0.4 annualized is about 0.021 a day: below it, the position stops at the cap.
    calm = {"aaa": _series("aaa", np.array([0.01 if i % 2 == 0 else -0.01 for i in range(100)]))}
    assert strategy.scale(calm["aaa"], day) == 1.0
    assert _scaled(max_scale=0.5).scale(calm["aaa"], day) == 0.5


class _Fixed:
    def __init__(self, signals: list[Signal]) -> None:
        self.signals = signals

    def generate_signals(self, bars, as_of):
        return self.signals


def test_signals_carry_their_scale_flat_ones_pass_and_unestimated_ones_drop() -> None:
    day = _FIRST + timedelta(days=100)
    noisy = _series("aaa", np.random.default_rng(1).normal(0.0, 0.05, 100))
    constant = _series("bbb", np.zeros(100))
    short_history = _series("ccc", np.full(10, 0.01))
    flat = _series("ddd", np.full(100, 0.01))

    def signal(instrument_id: str, direction: str) -> Signal:
        return Signal(instrument_id=instrument_id, ts=day, direction=direction, strength=0.1)

    strategy = VolatilityTargeted(
        inner=_Fixed(
            [
                signal("aaa", "short"),
                signal("bbb", "long"),
                signal("ccc", "long"),
                signal("ddd", "flat"),
            ]
        ),
        estimator=RollingVolatility(window_days=30),
        target_volatility=0.4,
        max_scale=1.0,
        periods_per_year=365,
    )

    signals = strategy.generate_signals(
        {"aaa": noisy, "bbb": constant, "ccc": short_history, "ddd": flat}, day
    )

    assert [(s.instrument_id, s.direction) for s in signals] == [("aaa", "short"), ("ddd", "flat")]
    assert signals[0].weight == strategy.scale(noisy, day)
    assert signals[1].weight is None


def test_the_scale_reads_no_bar_after_the_decision_day() -> None:
    bars = _bars()
    day = date(2018, 6, 1)
    changed = {
        instrument_id: [
            replace(bar, close=bar.close * 2.0) if bar.ts > day else bar for bar in series
        ]
        for instrument_id, series in bars.items()
    }

    assert _scaled().generate_signals(bars, day) == _scaled().generate_signals(changed, day)


def test_at_the_cap_every_day_the_scaled_strategy_is_the_unscaled_one() -> None:
    bars = _bars()
    # A target no estimate can reach: every scale is 1.
    at_cap = _run(_scaled(target=1e6), ScaledEqualWeight(), bars)
    unscaled = _run(TimeSeriesMomentum(lookback_days=60), EqualWeightBySign(), bars)

    assert [s.equity for s in at_cap.snapshots] == [s.equity for s in unscaled.snapshots]


def test_scaling_cuts_exposure_where_volatility_is_high() -> None:
    bars = _bars()
    run = _run(_scaled(target=0.4), ScaledEqualWeight(), bars)

    gross = [sum(abs(w) for w in s.positions.values()) for s in run.snapshots if s.positions]
    assert max(gross) == pytest.approx(1.0)  # calm periods: both at the cap
    assert min(gross) < 0.5  # turbulent periods: well below it
    assert all(g <= 1.0 + 1e-12 for g in gross)


def test_both_engines_trade_the_scaled_strategy_alike() -> None:
    bars = _bars()
    vectorized = _run(_scaled(), ScaledEqualWeight(), bars)
    event_driven = run_event_driven(
        strategy=_scaled(),
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
        sizer=ScaledEqualWeight(),
    )

    assert any(snapshot.traded for snapshot in vectorized.snapshots)
    assert max_equity_difference(vectorized, event_driven.run) < 1e-9


@pytest.mark.parametrize(
    ("target", "max_scale", "message"),
    [(0.0, 1.0, "target volatility"), (0.4, 1.5, r"\(0, 1\]"), (0.4, 0.0, r"\(0, 1\]")],
)
def test_no_leverage_and_a_positive_target(target, max_scale, message) -> None:
    with pytest.raises(ValueError, match=message):
        _scaled(target=target, max_scale=max_scale)
