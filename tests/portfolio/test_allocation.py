import numpy as np
import pytest

from quantlab.portfolio.allocation import (
    ALLOCATION_RULES,
    EqualWeight,
    InverseVolatility,
    RiskParity,
    RiskParityDidNotConvergeError,
    diversification_ratio,
    eligible_sleeves,
    risk_contributions,
)

_ALL = np.array([True, True, True])


def _uncorrelated(sigmas: list[float], periods: int = 4_000, seed: int = 1) -> np.ndarray:
    """Returns with the given volatilities and sample correlation exactly 0."""
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(periods, len(sigmas)))
    raw -= raw.mean(axis=0)
    # Whiten: sample covariance becomes the identity, then scale each column.
    whitened = raw @ np.linalg.inv(np.linalg.cholesky(np.cov(raw, rowvar=False)).T)
    return whitened * np.array(sigmas)


def test_equal_weight_splits_among_the_eligible_sleeves_only() -> None:
    window = _uncorrelated([0.01, 0.02, 0.03])

    weights = EqualWeight().weights(window, np.array([True, False, True]))

    assert weights.tolist() == [0.5, 0.0, 0.5]


def test_inverse_volatility_of_volatilities_1_and_2_is_two_thirds_one_third() -> None:
    window = _uncorrelated([0.01, 0.02])

    weights = InverseVolatility().weights(window, np.array([True, True]))

    assert weights == pytest.approx([2 / 3, 1 / 3], rel=1e-12)


def test_risk_parity_of_uncorrelated_sleeves_is_inverse_volatility() -> None:
    window = _uncorrelated([0.01, 0.02, 0.04])

    parity = RiskParity().weights(window, _ALL)

    assert parity == pytest.approx(InverseVolatility().weights(window, _ALL), rel=1e-10)
    assert parity == pytest.approx(np.array([4, 2, 1]) / 7, rel=1e-10)


def test_risk_parity_of_two_sleeves_is_inverse_volatility_whatever_their_correlation() -> None:
    rng = np.random.default_rng(3)
    common = rng.normal(size=2_000)
    window = np.column_stack(
        [0.01 * (common + 0.3 * rng.normal(size=2_000)), 0.03 * (common + rng.normal(size=2_000))]
    )
    both = np.array([True, True])

    assert RiskParity().weights(window, both) == pytest.approx(
        InverseVolatility().weights(window, both), rel=1e-10
    )


def test_risk_parity_equalizes_risk_contributions_of_correlated_sleeves() -> None:
    # Two momentum-like sleeves moving together and one that does not: inverse
    # volatility gives the pair two thirds of the capital, risk parity less.
    rng = np.random.default_rng(5)
    trend = rng.normal(size=3_000)
    window = 0.02 * np.column_stack(
        [
            trend + 0.2 * rng.normal(size=3_000),
            trend + 0.2 * rng.normal(size=3_000),
            rng.normal(size=3_000),
        ]
    )
    covariance = np.cov(window, rowvar=False)

    parity = RiskParity().weights(window, _ALL)

    assert risk_contributions(parity, covariance) == pytest.approx([1 / 3] * 3, rel=1e-8)
    assert parity.sum() == pytest.approx(1.0, rel=1e-14)
    assert parity[2] > InverseVolatility().weights(window, _ALL)[2]


def test_rules_give_nothing_without_an_eligible_sleeve() -> None:
    window = _uncorrelated([0.01, 0.02, 0.03])

    for rule in ALLOCATION_RULES.values():
        assert rule.weights(window, np.zeros(3, dtype=bool)).tolist() == [0.0, 0.0, 0.0]


def test_every_rule_gives_non_negative_weights_summing_to_one() -> None:
    window = np.random.default_rng(8).normal(0.0, 0.01, (90, 4))
    eligible = np.array([True, True, False, True])

    for name, rule in ALLOCATION_RULES.items():
        weights = rule.weights(window, eligible)
        assert (weights >= 0.0).all(), name
        assert weights[2] == 0.0, name
        assert weights.sum() == pytest.approx(1.0, rel=1e-12), name


def test_a_sleeve_is_eligible_from_min_days_after_its_first_return() -> None:
    history = np.zeros((200, 3))
    rng = np.random.default_rng(2)
    history[:, 0] = rng.normal(0.0, 0.01, 200)  # trading all along
    history[150:, 1] = rng.normal(0.0, 0.01, 50)  # started 50 days ago
    history[10:40, 2] = rng.normal(0.0, 0.01, 30)  # traded, then flat since

    assert eligible_sleeves(history, window=90, min_days=60).tolist() == [True, False, False]
    # Flat within the window: no variance to estimate, whatever its past.
    assert eligible_sleeves(history, window=170, min_days=60).tolist() == [True, False, True]
    assert eligible_sleeves(history, window=90, min_days=50).tolist() == [True, True, False]


def test_no_sleeve_is_eligible_without_history() -> None:
    assert eligible_sleeves(np.zeros((0, 2)), window=90, min_days=60).tolist() == [False, False]


def test_a_sleeve_flat_part_of_the_window_stays_eligible() -> None:
    history = np.zeros((120, 1))
    history[::3, 0] = np.random.default_rng(4).normal(0.0, 0.01, 40)  # a pair in and out

    assert eligible_sleeves(history, window=90, min_days=60).tolist() == [True]


def test_diversification_ratio_is_one_for_identical_sleeves_and_root_k_for_uncorrelated() -> None:
    identical = np.full((3, 3), 0.0004)
    uncorrelated = np.diag([0.0004, 0.0004, 0.0004])
    equal = np.full(3, 1 / 3)

    assert diversification_ratio(equal, identical) == pytest.approx(1.0)
    assert diversification_ratio(equal, uncorrelated) == pytest.approx(np.sqrt(3))
    assert diversification_ratio(equal, np.zeros((3, 3))) is None


def test_risk_parity_reports_non_convergence() -> None:
    window = np.random.default_rng(9).normal(0.0, 0.01, (90, 3))
    window[:, 1] += 0.9 * window[:, 0]

    with pytest.raises(RiskParityDidNotConvergeError, match="did not converge in 1 sweeps"):
        RiskParity(max_sweeps=1).weights(window, _ALL)
