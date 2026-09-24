from math import comb

import numpy as np
import pytest
from pydantic import ValidationError

from quantlab.validation.cpcv import (
    CpcvSettings,
    best_column,
    cpcv_of_selection,
    cpcv_paths,
    cpcv_splits,
    group_bounds,
)


def test_groups_are_contiguous_and_the_first_ones_one_longer() -> None:
    assert group_bounds(103, 10) == [
        (0, 11),
        (11, 22),
        (22, 33),
        *((33 + 10 * i, 43 + 10 * i) for i in range(7)),
    ]
    with pytest.raises(ValueError, match="10 groups need at least 10 periods"):
        group_bounds(9, 10)


@pytest.mark.parametrize(("groups", "test_groups"), [(10, 2), (6, 2), (6, 3), (5, 1)])
def test_there_are_c_n_k_splits_and_k_c_n_k_over_n_paths(groups: int, test_groups: int) -> None:
    splits = cpcv_splits(120, groups, test_groups, purge=0, embargo=0)
    paths = cpcv_paths(groups, test_groups)

    assert len(splits) == comb(groups, test_groups)
    assert len(paths) == test_groups * comb(groups, test_groups) // groups
    for path in paths:
        # Every group comes from a split that tests it: the path covers each period once.
        assert all(group in splits[index].test_groups for group, index in enumerate(path))
    # And every split's test groups are used by exactly one path each.
    uses = sorted((index, group) for path in paths for group, index in enumerate(path))
    assert uses == sorted((i, g) for i, split in enumerate(splits) for g in split.test_groups)


def test_training_sets_leave_out_the_purge_before_and_the_embargo_after_each_test_group() -> None:
    [split] = [s for s in cpcv_splits(100, 10, 2, purge=2, embargo=3) if s.test_groups == (3, 7)]

    test = np.flatnonzero(split.test)
    train = set(np.flatnonzero(split.train))
    assert list(test) == [*range(30, 40), *range(70, 80)]
    assert {28, 29, 68, 69} & train == set()  # purged
    assert {40, 41, 42, 80, 81, 82} & train == set()  # embargoed
    assert {27, 43, 67, 83} <= train
    assert len(train) == 100 - 20 - 4 - 6


def test_purge_and_embargo_stop_at_the_ends_of_the_period() -> None:
    [first] = [s for s in cpcv_splits(50, 5, 1, purge=3, embargo=4) if s.test_groups == (0,)]
    [last] = [s for s in cpcv_splits(50, 5, 1, purge=3, embargo=4) if s.test_groups == (4,)]

    assert np.flatnonzero(first.train)[0] == 14  # test 0-9, embargo 10-13
    assert np.flatnonzero(last.train)[-1] == 36  # purge 37-39, test 40-49


def test_a_split_left_without_training_periods_is_an_error() -> None:
    with pytest.raises(ValueError, match=r"Split \(0, 1\) has no training periods"):
        cpcv_splits(30, 3, 2, purge=0, embargo=10)


def test_settings_validate_their_ranges() -> None:
    settings = CpcvSettings(groups=10, test_groups=2, purge_days=1, embargo_fraction=0.01)

    assert settings.embargo(2190) == 22
    with pytest.raises(ValidationError, match="test_groups must be below groups"):
        CpcvSettings(groups=4, test_groups=4, purge_days=0, embargo_fraction=0.0)
    with pytest.raises(ValidationError):
        CpcvSettings(groups=10, test_groups=2, purge_days=0, embargo_fraction=0.5)


def test_the_best_column_ties_to_the_earlier_one_and_needs_a_sharpe() -> None:
    same = np.tile(np.array([[0.01], [0.02], [-0.01]]), (1, 3))

    assert best_column(same) == 0
    assert best_column(np.zeros((5, 2))) is None


_SETTINGS = CpcvSettings(groups=10, test_groups=2, purge_days=1, embargo_fraction=0.01)
_LABELS = ["30", "90", "180", "365"]


def test_a_grid_with_one_clearly_better_value_chooses_it_and_its_paths_earn() -> None:
    rng = np.random.default_rng(7)
    returns = rng.normal(0.0, 0.01, (2000, 4))
    returns[:, 2] += 0.002  # "180" has a lasting edge

    result = cpcv_of_selection(returns, _LABELS, _SETTINGS, periods_per_year=365)

    assert (result.n_splits, result.n_paths, result.embargo) == (45, 9, 20)
    assert result.choice_shares["180"] == 1.0
    assert result.choices == ["180"] * 45
    assert result.positive_share == 1.0
    assert result.median_sharpe > 2.0


def test_on_noise_the_paths_centre_on_zero() -> None:
    medians = np.array(
        [
            cpcv_of_selection(
                np.random.default_rng(seed).normal(0.0, 0.01, (1500, 4)), _LABELS, _SETTINGS, 365
            ).median_sharpe
            for seed in range(200)
        ]
    )

    # Choosing on noise earns nothing out of sample: about 3 standard errors of slack.
    assert abs(medians.mean()) < 3 * medians.std() / np.sqrt(len(medians))
    assert 0.4 < (medians > 0).mean() < 0.6


def test_a_path_takes_each_group_from_its_own_split_choice() -> None:
    # Two values: "a" earns only in the first half, "b" only in the second. Each split
    # chooses by its training set, so paths mix the two; checked against a direct build.
    rng = np.random.default_rng(3)
    returns = rng.normal(0.0, 0.01, (600, 2))
    returns[:300, 0] += 0.004
    returns[300:, 1] += 0.004
    settings = CpcvSettings(groups=6, test_groups=2, purge_days=0, embargo_fraction=0.0)

    result = cpcv_of_selection(returns, ["a", "b"], settings, periods_per_year=1)

    splits = cpcv_splits(600, 6, 2, 0, 0)
    for path, sharpe in zip(cpcv_paths(6, 2), result.path_sharpes, strict=True):
        series = np.concatenate(
            [
                returns[100 * g : 100 * (g + 1), ["a", "b"].index(result.choices[index])]
                for g, index in enumerate(path)
            ]
        )
        assert sharpe == pytest.approx(series.mean() / series.std(ddof=1))
    assert {
        choice
        for split, choice in zip(splits, result.choices, strict=True)
        if set(split.test_groups) == {0, 1}
    } == {"b"}  # trained on the second half's edge


def test_a_split_without_any_sharpe_holds_nothing_in_its_test_periods() -> None:
    returns = np.zeros((300, 2))
    returns[:100] = np.random.default_rng(1).normal(0.0, 0.01, (100, 2))
    settings = CpcvSettings(groups=3, test_groups=2, purge_days=0, embargo_fraction=0.0)

    result = cpcv_of_selection(returns, ["a", "b"], settings, periods_per_year=1)

    # Splits (0, 1) and (0, 2) train on a group of zeros only: no Sharpe, no choice.
    assert result.choices[:2] == [None, None]
    assert result.choices[2] is not None
    assert sum(result.choice_shares.values()) == pytest.approx(1 / 3)
