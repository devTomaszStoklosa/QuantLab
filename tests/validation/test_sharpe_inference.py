import math
from statistics import NormalDist

import numpy as np
import pytest

from quantlab.validation.sharpe_inference import (
    SharpeStatistics,
    deflated_sharpe_ratio,
    expected_max_sharpe,
    null_sharpe_variance,
    probabilistic_sharpe_ratio,
    sharpe_statistics,
)


def _statistics(sharpe: float, n: int, skewness: float = 0.0, kurtosis: float = 3.0):
    return SharpeStatistics(sharpe=sharpe, n_returns=n, skewness=skewness, kurtosis=kurtosis)


def test_deflated_sharpe_reproduces_the_worked_example_of_the_paper() -> None:
    # Bailey and Lopez de Prado (2014): 100 trials whose annualized Sharpe ratios
    # vary with variance 0.5, 1 250 daily returns (250 a year), annualized Sharpe
    # 2.5, skewness -3, kurtosis 10.
    threshold = expected_max_sharpe(n_trials=100, variance=0.5 / 250)
    best = _statistics(2.5 / math.sqrt(250), 1_250, skewness=-3.0, kurtosis=10.0)

    assert threshold == pytest.approx(0.1132, abs=5e-5)
    assert probabilistic_sharpe_ratio(best, threshold) == pytest.approx(0.9004, abs=5e-5)


def test_normal_returns_use_the_standard_error_of_lo_2002() -> None:
    statistics = _statistics(0.05, 500)

    expected = NormalDist().cdf(0.05 * math.sqrt(499) / math.sqrt(1 + 0.05**2 / 2))
    assert probabilistic_sharpe_ratio(statistics) == pytest.approx(expected)


def test_psr_is_one_half_at_the_benchmark() -> None:
    assert probabilistic_sharpe_ratio(_statistics(0.1, 300), benchmark=0.1) == pytest.approx(0.5)


def test_longer_history_makes_a_positive_sharpe_more_convincing() -> None:
    short = probabilistic_sharpe_ratio(_statistics(0.03, 250))
    long = probabilistic_sharpe_ratio(_statistics(0.03, 2_500))

    assert 0.5 < short < long


def test_negative_skew_and_fat_tails_lower_the_psr_of_a_positive_sharpe() -> None:
    normal = probabilistic_sharpe_ratio(_statistics(0.1, 500))
    crash_prone = probabilistic_sharpe_ratio(_statistics(0.1, 500, skewness=-2.0, kurtosis=12.0))

    assert crash_prone < normal


def test_psr_is_undefined_when_the_variance_term_is_not_positive() -> None:
    assert probabilistic_sharpe_ratio(_statistics(1.0, 100, skewness=5.0, kurtosis=1.0)) is None


def test_sharpe_statistics_match_their_definitions() -> None:
    returns = [0.01, -0.02, 0.03, 0.0, 0.015]
    values = np.array(returns)
    centered = values - values.mean()

    statistics = sharpe_statistics(returns)

    assert statistics.sharpe == pytest.approx(values.mean() / values.std(ddof=1))
    assert statistics.n_returns == 5
    assert statistics.skewness == pytest.approx(np.mean(centered**3) / np.mean(centered**2) ** 1.5)
    assert statistics.kurtosis == pytest.approx(np.mean(centered**4) / np.mean(centered**2) ** 2)


def test_sharpe_statistics_are_undefined_for_short_or_flat_series() -> None:
    assert sharpe_statistics([0.01, 0.02]) is None
    assert sharpe_statistics([0.0, 0.0, 0.0, 0.0]) is None


def test_one_trial_has_a_zero_threshold_so_dsr_equals_psr_at_zero() -> None:
    statistics = _statistics(0.04, 800, skewness=-0.5, kurtosis=6.0)

    assert expected_max_sharpe(1, 0.01) == 0.0
    assert deflated_sharpe_ratio(statistics, 1) == probabilistic_sharpe_ratio(statistics, 0.0)


def test_more_trials_raise_the_threshold_and_lower_the_dsr() -> None:
    statistics = _statistics(0.04, 800)

    thresholds = [expected_max_sharpe(n, null_sharpe_variance(800)) for n in (2, 5, 20)]
    deflated = [deflated_sharpe_ratio(statistics, n) for n in (1, 2, 5, 20)]

    assert thresholds == sorted(thresholds)
    assert deflated == sorted(deflated, reverse=True)


def test_threshold_approximates_the_best_sharpe_of_trials_without_edge() -> None:
    # Monte Carlo: 10 trials of 500 zero-mean normal returns, 2 000 repetitions.
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.01, size=(2_000, 10, 500))
    sharpe = returns.mean(axis=2) / returns.std(axis=2, ddof=1)
    simulated = sharpe.max(axis=1).mean()

    predicted = expected_max_sharpe(10, null_sharpe_variance(500))

    # The closed form overstates E[max of 10 normals] (1.539) slightly (1.575).
    assert predicted == pytest.approx(simulated, rel=0.05)


@pytest.mark.parametrize(("n_trials", "variance"), [(0, 0.01), (2, -0.01)])
def test_expected_max_sharpe_rejects_invalid_input(n_trials: int, variance: float) -> None:
    with pytest.raises(ValueError):
        expected_max_sharpe(n_trials, variance)


def test_null_variance_needs_two_returns() -> None:
    assert null_sharpe_variance(101) == pytest.approx(0.01)
    with pytest.raises(ValueError):
        null_sharpe_variance(1)
