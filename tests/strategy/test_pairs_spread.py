import math
from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.run import BacktestRun
from quantlab.backtest.sizing import PairWeights
from quantlab.backtest.vectorized.engine import run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.cointegration import hedge_ratio
from quantlab.strategy.pairs_spread import PairsSpreadReversion, pair_states, spread_path

_START = date(2020, 1, 1)
_WINDOW = 60


def _series(seed: int, n: int = 400, phi: float = 0.9, cointegrated: bool = True):
    """log x a random walk; log y = -2 + 0.9 log x + an AR(1) spread (or its own walk)."""
    rng = np.random.default_rng(seed)
    log_x = math.log(20_000.0) + np.cumsum(rng.normal(0.0, 0.035, n))
    if not cointegrated:
        return math.log(1_500.0) + np.cumsum(rng.normal(0.0, 0.035, n)), log_x
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = phi * spread[t - 1] + rng.normal(0.0, 0.02)
    return -2.0 + 0.9 * log_x + spread, log_x


def _bars(log_y: np.ndarray, log_x: np.ndarray, skip: set[int] = frozenset()):
    def leg(instrument_id: str, values: np.ndarray, skipped: set[int]) -> list[PriceBar]:
        return [
            PriceBar(
                instrument_id=instrument_id,
                ts=_START + timedelta(days=i),
                open=float(np.exp(v)),
                high=float(np.exp(v)),
                low=float(np.exp(v)),
                close=float(np.exp(v)),
                volume=1.0,
                source="test",
            )
            for i, v in enumerate(values)
            if i not in skipped
        ]

    return {"eth": leg("eth", log_y, skip), "btc": leg("btc", log_x, set())}


def _strategy(max_coint_p_value: float | None = None) -> PairsSpreadReversion:
    return PairsSpreadReversion("eth", "btc", _WINDOW, 2.0, 0.0, max_coint_p_value)


def test_spread_path_matches_an_ols_fit_on_each_window() -> None:
    log_y, log_x = _series(seed=1)

    beta, z = spread_path(log_y, log_x, _WINDOW)

    assert np.isnan(beta[: _WINDOW - 1]).all() and np.isnan(z[: _WINDOW - 1]).all()
    for end in (_WINDOW - 1, 200, 399):
        window = slice(end - _WINDOW + 1, end + 1)
        alpha, slope = hedge_ratio(log_y[window], log_x[window])
        residuals = log_y[window] - alpha - slope * log_x[window]
        assert beta[end] == pytest.approx(slope, abs=1e-9)
        assert z[end] == pytest.approx(residuals[-1] / residuals.std(ddof=1), abs=1e-9)


def test_state_machine_enters_at_the_threshold_and_exits_at_the_mean() -> None:
    z = np.array([np.nan, 0.5, 2.1, 1.0, 0.1, -0.2, -2.5, -1.0, 0.3, 2.0, -2.2, np.nan, -3.0])

    states = pair_states(z, entry_z=2.0, exit_z=0.0, may_enter=lambda i: True)

    # 2.1 opens a short spread held until z <= 0 (-0.2); -2.5 opens a long one
    # closed at 0.3; 2.0 opens a short and -2.2 closes it and opens a long the
    # same day; an undefined z closes everything.
    assert states.tolist() == [0, 0, -1, -1, -1, 0, 1, 1, 0, -1, 1, 0, 1]


def test_the_entry_gate_blocks_entries_but_never_exits() -> None:
    z = np.array([2.5, 1.0, -0.5, -2.5, -1.0])

    gated = pair_states(z, 2.0, 0.0, may_enter=lambda i: i == 0)

    assert gated.tolist() == [-1, -1, 0, 0, 0]


def test_signals_carry_both_legs_with_hedge_ratio_weights() -> None:
    log_y, log_x = _series(seed=2)
    bars = _bars(log_y, log_x)
    beta, z = spread_path(log_y, log_x, _WINDOW)
    states = pair_states(z, 2.0, 0.0, lambda i: True)
    day = int(np.flatnonzero(states == 1)[0])

    signals = _strategy().generate_signals(bars, _START + timedelta(days=day))

    by_leg = {signal.instrument_id: signal for signal in signals}
    assert (by_leg["eth"].direction, by_leg["btc"].direction) == ("long", "short")
    assert by_leg["eth"].weight == pytest.approx(1.0 / (1.0 + beta[day]))
    assert by_leg["btc"].weight == pytest.approx(beta[day] / (1.0 + beta[day]))
    assert by_leg["eth"].weight + by_leg["btc"].weight == pytest.approx(1.0)


def test_signals_ignore_everything_after_the_signal_date() -> None:
    log_y, log_x = _series(seed=3)
    as_of = _START + timedelta(days=250)
    changed_future = log_y.copy()
    changed_future[251:] += 5.0  # a spread blow-out right after as_of

    honest = _strategy(0.05).generate_signals(_bars(log_y, log_x), as_of)
    with_future = _strategy(0.05).generate_signals(_bars(changed_future, log_x), as_of)

    assert honest == with_future


def test_no_signal_without_both_legs_on_the_day() -> None:
    log_y, log_x = _series(seed=4)
    bars = _bars(log_y, log_x, skip={300})

    assert _strategy().generate_signals(bars, _START + timedelta(days=300)) == []


def test_a_missing_leg_in_the_input_is_an_error() -> None:
    log_y, log_x = _series(seed=4)
    bars = _bars(log_y, log_x)
    del bars["btc"]

    with pytest.raises(ValueError, match="btc"):
        _strategy().generate_signals(bars, _START + timedelta(days=100))


def _held_days(bars, max_coint_p_value: float | None) -> tuple[int, BacktestRun]:
    result = run(
        strategy=_strategy(max_coint_p_value),
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=_START + timedelta(days=_WINDOW),
        end=_START + timedelta(days=399),
        seed=0,
        git_sha="test",
        strategy_name="pairs",
        strategy_params={},
        sizer=PairWeights(),
    )
    return sum(1 for snapshot in result.snapshots if snapshot.positions), result


def test_the_cointegration_filter_trades_less_where_there_is_none() -> None:
    unrelated = _bars(*_series(seed=5, cointegrated=False))

    unfiltered, _ = _held_days(unrelated, None)
    filtered, _ = _held_days(unrelated, 0.05)

    assert filtered < unfiltered


def test_a_strongly_mean_reverting_spread_earns_before_costs() -> None:
    days, result = _held_days(_bars(*_series(seed=6, phi=0.8)), 0.05)

    assert days > 0
    assert result.snapshots[-1].equity > 1.0
    # Gross exposure 1, market neutral: one leg long, the other short.
    for snapshot in result.snapshots:
        if snapshot.positions:
            weights = snapshot.positions.values()
            assert sum(abs(w) for w in weights) == pytest.approx(1.0)
            assert min(weights) < 0 < max(weights)
