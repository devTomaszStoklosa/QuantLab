from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from quantlab.core.data.provider import PriceBar
from quantlab.risk.volatility import EwmaVolatility, RollingVolatility, trailing_returns

_FIRST = date(2026, 1, 1)


def _bars(returns: list[float] | np.ndarray) -> list[PriceBar]:
    closes = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + np.asarray(returns)]))
    return [
        PriceBar(
            instrument_id="btc-usdt",
            ts=_FIRST + timedelta(days=i),
            open=float(close),
            high=float(close),
            low=float(close),
            close=float(close),
            volume=1.0,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def _day(returns: int) -> date:
    """The day of the bar after `returns` returns."""
    return _FIRST + timedelta(days=returns)


def test_rolling_volatility_of_alternating_returns_is_known_upfront() -> None:
    x, window = 0.03, 20
    bars = _bars([x if i % 2 == 0 else -x for i in range(60)])

    sigma = RollingVolatility(window_days=window).daily_volatility(bars, _day(60))

    # Mean 0 over an even window; the sample standard deviation divides by n - 1.
    assert sigma == pytest.approx(x * np.sqrt(window / (window - 1)), rel=1e-12)


def test_ewma_volatility_matches_an_exponentially_weighted_variance() -> None:
    returns = np.random.default_rng(7).normal(0.0, 0.03, 400)
    bars = _bars(returns)
    estimator = EwmaVolatility(center_of_mass_days=60, window_days=365)

    sigma = estimator.daily_volatility(bars, _day(400))

    # pandas normalizes the same weights over the values it is given (adjust=True).
    window = pd.Series(returns[-365:])
    expected = np.sqrt(window.ewm(com=60).var(bias=True).iloc[-1])
    assert sigma == pytest.approx(expected, rel=1e-10)


def test_ewma_weights_have_the_given_center_of_mass() -> None:
    estimator = EwmaVolatility(center_of_mass_days=60, window_days=3000)

    ages = np.arange(3000 - 1, -1, -1)  # the newest return has age 0

    assert float(estimator._weights @ ages) == pytest.approx(60.0, rel=1e-9)
    assert float(estimator._weights.sum()) == pytest.approx(1.0, rel=1e-12)


@pytest.mark.parametrize(
    "estimator", [RollingVolatility(window_days=30), EwmaVolatility(60, window_days=30)]
)
def test_no_estimate_without_a_full_window_or_a_bar_for_the_day(estimator) -> None:
    bars = _bars(np.full(40, 0.01))

    assert estimator.daily_volatility(bars, _day(29)) is None  # 29 returns
    assert estimator.daily_volatility(bars, _day(30)) is not None
    assert estimator.daily_volatility(bars, _day(41)) is None  # after the last bar
    assert trailing_returns(bars, _FIRST - timedelta(days=1), 1) is None


@pytest.mark.parametrize(
    "estimator", [RollingVolatility(window_days=30), EwmaVolatility(60, window_days=30)]
)
def test_an_estimate_reads_no_bar_after_its_day(estimator) -> None:
    bars = _bars(np.random.default_rng(3).normal(0.0, 0.02, 100))
    changed = [replace(bar, close=bar.close * 3.0) if bar.ts > _day(60) else bar for bar in bars]

    assert estimator.daily_volatility(bars, _day(60)) == estimator.daily_volatility(
        changed, _day(60)
    )


@pytest.mark.parametrize(
    "estimator", [RollingVolatility(window_days=30), EwmaVolatility(60, window_days=30)]
)
def test_an_estimate_does_not_depend_on_where_the_history_starts(estimator) -> None:
    bars = _bars(np.random.default_rng(5).normal(0.0, 0.02, 200))

    # A holdout fetches from its start minus the warm-up: exactly the window.
    assert estimator.daily_volatility(bars, _day(200)) == estimator.daily_volatility(
        bars[-31:], _day(200)
    )


def test_constant_prices_have_zero_volatility() -> None:
    bars = _bars(np.zeros(40))

    assert RollingVolatility(window_days=30).daily_volatility(bars, _day(40)) == 0.0
    assert EwmaVolatility(60, window_days=30).daily_volatility(bars, _day(40)) == 0.0


def test_estimators_refuse_windows_without_a_variance() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        RollingVolatility(window_days=1)
    with pytest.raises(ValueError, match="at least 2"):
        EwmaVolatility(60, window_days=1)
    with pytest.raises(ValueError, match="center of mass"):
        EwmaVolatility(0, window_days=30)
