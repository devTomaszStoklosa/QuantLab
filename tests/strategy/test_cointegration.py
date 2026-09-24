import math

import numpy as np
import pytest

from quantlab.strategy.cointegration import engle_granger, half_life, hedge_ratio


def _cointegrated_pair(seed: int, n: int = 2_000, phi: float = 0.9, beta: float = 0.8):
    """log x is a random walk; y = 0.5 + beta * x + an AR(1) spread with coefficient phi."""
    rng = np.random.default_rng(seed)
    x = 10.0 + np.cumsum(rng.normal(0.0, 0.03, n))
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = phi * spread[t - 1] + rng.normal(0.0, 0.01)
    return 0.5 + beta * x + spread, x


def test_hedge_ratio_recovers_an_exact_line() -> None:
    x = np.array([1.0, 2.0, 4.0, 7.0])

    alpha, beta = hedge_ratio(1.0 + 0.8 * x, x)

    assert (alpha, beta) == (pytest.approx(1.0), pytest.approx(0.8))


def test_a_cointegrated_pair_is_detected_with_its_hedge_ratio_and_half_life() -> None:
    y, x = _cointegrated_pair(seed=3)

    result = engle_granger(y, x)

    assert result.beta == pytest.approx(0.8, abs=0.02)
    assert result.p_value < 0.01
    assert result.statistic < result.critical_values["1%"]
    # AR(1) with phi 0.9: deviations halve in -ln 2 / ln 0.9 = 6.58 periods.
    assert result.half_life == pytest.approx(-math.log(2) / math.log(0.9), rel=0.2)
    assert result.n_observations == 2_000


def test_independent_random_walks_are_rarely_called_cointegrated() -> None:
    rejections = 0
    for seed in range(40):
        rng = np.random.default_rng(100 + seed)
        y = np.cumsum(rng.normal(0.0, 0.03, 500))
        x = np.cumsum(rng.normal(0.0, 0.03, 500))
        rejections += engle_granger(y, x).p_value < 0.05

    # The test's size is 5%; allow sampling noise over 40 pairs.
    assert rejections <= 6


def test_critical_values_are_ordered_from_strictest() -> None:
    result = engle_granger(*_cointegrated_pair(seed=4, n=500))

    assert list(result.critical_values) == ["1%", "5%", "10%"]
    assert (
        result.critical_values["1%"] < result.critical_values["5%"] < result.critical_values["10%"]
    )


def test_half_life_is_undefined_for_a_spread_that_does_not_revert() -> None:
    explosive = 1.01 ** np.arange(200)
    alternating = np.array([1.0, -1.0] * 100)

    assert half_life(explosive) is None
    assert half_life(alternating) is None


@pytest.mark.parametrize(
    ("y", "x", "message"),
    [
        ([1.0, 2.0, 3.0], [1.0, 2.0], "same length"),
        ([1.0, 2.0], [1.0, 2.0], "at least 3"),
        ([1.0, 2.0, 3.0], [5.0, 5.0, 5.0], "no variance"),
    ],
)
def test_hedge_ratio_rejects_unusable_input(y: list, x: list, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        hedge_ratio(np.array(y), np.array(x))
