"""AC-1: with the vectorized engine's assumptions both engines give the same run."""

from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import CloseExecution
from quantlab.backtest.run import BacktestRun
from quantlab.backtest.vectorized.engine import run as vectorized_run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.realistic import RealisticCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

_START = date(2026, 1, 1)
_DAYS = 300
_TOLERANCE = 1e-12


def _random_walk_bars(instruments: tuple[str, ...], seed: int) -> dict[str, list[PriceBar]]:
    rng = np.random.default_rng(seed)
    bars = {}
    for instrument_id in instruments:
        price, series = 100.0, []
        for day in range(_DAYS):
            price *= 1.0 + rng.normal(0.0, 0.04)
            series.append(
                PriceBar(
                    instrument_id=instrument_id,
                    ts=_START + timedelta(days=day),
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=1.0,
                    source="test",
                )
            )
        bars[instrument_id] = series
    return bars


class _ScriptedFlips:
    """Long, short and flat by a fixed pattern per instrument, with flips and exits."""

    _PATTERN = ("long", "long", "short", "flat", "short", "long", "flat", "flat")

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        day = (as_of - _START).days
        return [
            Signal(
                instrument_id=instrument_id,
                ts=as_of,
                direction=self._PATTERN[(day + offset) % len(self._PATTERN)],
                strength=0.0,
            )
            for offset, instrument_id in enumerate(sorted(bars))
        ]


def assert_same_run(expected: BacktestRun, actual: BacktestRun) -> None:
    assert len(actual.snapshots) == len(expected.snapshots)
    for want, got in zip(expected.snapshots, actual.snapshots, strict=True):
        assert got.ts == want.ts
        assert got.equity == pytest.approx(want.equity, rel=_TOLERANCE)
        assert got.cash == pytest.approx(want.cash, abs=_TOLERANCE)
        for field in ("positions", "costs", "traded"):
            got_values, want_values = getattr(got, field), getattr(want, field)
            assert got_values.keys() == want_values.keys(), (field, got.ts)
            for instrument_id, value in want_values.items():
                assert got_values[instrument_id] == pytest.approx(value, abs=_TOLERANCE)


_STRATEGIES = {
    "momentum": TimeSeriesMomentum(lookback_days=20),
    "reversal": ShortTermReversal(formation_days=5),
    "scripted-flips": _ScriptedFlips(),
}
_COST_MODELS = {
    "zero": ZeroCostModel(),
    "naive": NaiveCostModel(bps=10),
    "realistic": RealisticCostModel(fee_bps=10, k=0.05, vol_window=10),
}


@pytest.mark.parametrize("cost_name", sorted(_COST_MODELS))
@pytest.mark.parametrize("strategy_name", sorted(_STRATEGIES))
def test_close_execution_reproduces_the_vectorized_run(strategy_name: str, cost_name: str) -> None:
    bars = _random_walk_bars(("a", "b", "c"), seed=11)
    args = {
        "strategy": _STRATEGIES[strategy_name],
        "cost_model": _COST_MODELS[cost_name],
        "bars": bars,
        "universe_name": "parity",
        "start": _START + timedelta(days=25),
        "end": _START + timedelta(days=_DAYS - 1),
        "seed": 0,
        "git_sha": "parity",
        "strategy_name": strategy_name,
        "strategy_params": {},
    }

    expected = vectorized_run(**args)
    actual = event_driven_run(**args, execution=CloseExecution(), capital=100_000.0)

    assert_same_run(expected, actual.run)
    assert actual.run.cost_model_name == expected.cost_model_name


def test_normalized_run_does_not_depend_on_the_nominal_capital() -> None:
    bars = _random_walk_bars(("a", "b"), seed=5)
    args = {
        "strategy": TimeSeriesMomentum(lookback_days=10),
        "cost_model": RealisticCostModel(fee_bps=10, k=0.05, vol_window=10),
        "bars": bars,
        "universe_name": "parity",
        "start": _START + timedelta(days=15),
        "end": _START + timedelta(days=_DAYS - 1),
        "seed": 0,
        "git_sha": "parity",
        "strategy_name": "momentum",
        "strategy_params": {},
        "execution": CloseExecution(),
    }

    unit = event_driven_run(**args, capital=1.0)
    large = event_driven_run(**args, capital=250_000_000.0)

    assert_same_run(unit.run, large.run)
