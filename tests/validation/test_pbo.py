"""AC-4: PBO by CSCV - about 0.5 for noise, about 0 for a real edge."""

import numpy as np
import pytest

from quantlab.validation.pbo import probability_of_backtest_overfitting


def test_choosing_among_pure_noise_is_a_coin_flip_on_average() -> None:
    # A single noise matrix can land anywhere between 0.2 and 0.9 (the splits
    # share their data); the average over independent matrices sits at 0.5.
    results = [
        probability_of_backtest_overfitting(
            np.random.default_rng(seed).normal(0.0, 0.01, (1_600, 10))
        ).pbo
        for seed in range(20)
    ]

    assert np.mean(results) == pytest.approx(0.5, abs=0.1)


def test_a_configuration_with_a_real_edge_is_not_overfit() -> None:
    returns = np.random.default_rng(1).normal(0.0, 0.01, (1_600, 10))
    returns[:, 3] += 0.002  # Sharpe 0.2 a day, the rest none

    result = probability_of_backtest_overfitting(returns)

    assert result.pbo == 0.0
    assert result.logit_median > 0


def _two_blocks(first: tuple[float, float], second: tuple[float, float]) -> np.ndarray:
    # Two columns, two blocks of four days; within a block a column alternates
    # around its mean so its Sharpe there is mean / 0.01.
    noise = np.array([0.01, -0.01, 0.01, -0.01])
    return np.vstack(
        [
            np.column_stack([mean + noise for mean in first]),
            np.column_stack([mean + noise for mean in second]),
        ]
    )


def test_with_two_configurations_pbo_counts_splits_where_the_winner_flips() -> None:
    # A wins the first block, B the second: whichever block is in-sample, its
    # winner loses out of sample.
    flipping = probability_of_backtest_overfitting(
        _two_blocks((0.005, 0.001), (0.001, 0.005)), n_blocks=2
    )
    steady = probability_of_backtest_overfitting(
        _two_blocks((0.005, 0.001), (0.004, 0.002)), n_blocks=2
    )

    assert (flipping.pbo, flipping.n_splits) == (1.0, 2)
    assert steady.pbo == 0.0


def test_the_earliest_rows_that_do_not_fill_a_block_are_dropped() -> None:
    returns = np.random.default_rng(2).normal(0.0, 0.01, (1_615, 3))

    result = probability_of_backtest_overfitting(returns)

    assert (result.rows_used, result.n_blocks, result.n_splits) == (1_600, 16, 12_870)
    assert result.n_configurations == 3


def test_a_column_without_variance_scores_zero_and_ties_share_a_rank() -> None:
    # Both columns flat: every Sharpe is 0, the tie puts the winner at the
    # median (omega 0.5), which counts as overfit.
    result = probability_of_backtest_overfitting(np.zeros((32, 2)))

    assert result.pbo == 1.0
    assert result.logit_median == 0.0


@pytest.mark.parametrize(
    ("shape", "n_blocks", "message"),
    [
        ((100, 1), 16, "at least 2 configurations"),
        ((100, 3), 15, "even"),
        ((10, 3), 16, "at least 16 rows"),
        ((100,), 16, "T x N"),
    ],
)
def test_invalid_input_is_rejected(shape: tuple, n_blocks: int, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        probability_of_backtest_overfitting(np.zeros(shape), n_blocks=n_blocks)
