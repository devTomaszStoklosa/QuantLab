"""Combinatorial purged cross-validation of a parameter-selection procedure (q8, REQ-810..814).

Lopez de Prado (2018), Advances in Financial Machine Learning, ch. 12. The
training period's T periods form N contiguous groups; every choice of k groups
is a split's test set and the rest, less a purge before and an embargo after
each test group, its training set. The procedure chooses a grid value on each
training set, and that value's returns on the test set are out of sample. The
C(N, k) splits' test sets combine into k * C(N, k) / N paths, each a complete
out-of-sample history: many paths from one history, where walk-forward gives one.

The input is one series of net daily returns per grid value, each from one
backtest over the whole period. A split makes a single choice, so its test
returns are exactly the chosen value's backtest returns there; only the
switches between a path's segments go uncosted.
"""

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from pydantic import BaseModel, Field, model_validator


class CpcvSettings(BaseModel):
    """The frozen settings of a CPCV (q8 02-spec, CpcvSettings)."""

    groups: int = Field(ge=3)
    test_groups: int = Field(ge=1)
    purge_days: int = Field(ge=0)
    embargo_fraction: float = Field(ge=0.0, le=0.1)

    @model_validator(mode="after")
    def _fewer_test_groups(self) -> "CpcvSettings":
        if self.test_groups >= self.groups:
            raise ValueError("test_groups must be below groups")
        return self

    def embargo(self, n_periods: int) -> int:
        """Periods embargoed after each test group: the fraction of all periods, rounded up."""
        return math.ceil(self.embargo_fraction * n_periods)


@dataclass(frozen=True)
class CpcvSplit:
    test_groups: tuple[int, ...]
    train: np.ndarray  # bool mask over the periods
    test: np.ndarray  # bool mask over the periods


def group_bounds(n_periods: int, groups: int) -> list[tuple[int, int]]:
    """[start, end) of each of `groups` contiguous groups; the first T mod N are one longer."""
    if groups > n_periods:
        raise ValueError(f"{groups} groups need at least {groups} periods, got {n_periods}")
    size, longer = divmod(n_periods, groups)
    bounds, start = [], 0
    for group in range(groups):
        end = start + size + (1 if group < longer else 0)
        bounds.append((start, end))
        start = end
    return bounds


def cpcv_splits(
    n_periods: int, groups: int, test_groups: int, purge: int, embargo: int
) -> list[CpcvSplit]:
    """Every combination of `test_groups` groups as a test set, in lexicographic order
    (REQ-810), with training sets purged before and embargoed after each test group
    (REQ-811)."""
    bounds = group_bounds(n_periods, groups)
    splits = []
    for chosen in combinations(range(groups), test_groups):
        test = np.zeros(n_periods, dtype=bool)
        excluded = np.zeros(n_periods, dtype=bool)
        for group in chosen:
            start, end = bounds[group]
            test[start:end] = True
            excluded[max(0, start - purge) : start] = True
            excluded[end : min(n_periods, end + embargo)] = True
        train = ~test & ~excluded
        if not train.any():
            raise ValueError(f"Split {chosen} has no training periods left after purge and embargo")
        splits.append(CpcvSplit(test_groups=chosen, train=train, test=test))
    return splits


def cpcv_paths(groups: int, test_groups: int) -> list[list[int]]:
    """For each path, the split (index in cpcv_splits order) each group takes its test
    returns from: path j uses, for every group, the j-th split testing it (REQ-812)."""
    testing: list[list[int]] = [[] for _ in range(groups)]
    for index, chosen in enumerate(combinations(range(groups), test_groups)):
        for group in chosen:
            testing[group].append(index)
    n_paths = len(testing[0])  # C(N - 1, k - 1) = k * C(N, k) / N, the same for every group
    return [[testing[group][path] for group in range(groups)] for path in range(n_paths)]


def _sharpe(returns: np.ndarray) -> np.ndarray:
    """Per-period Sharpe (ddof=1) of each column; NaN without variance or with under 2 rows."""
    if len(returns) < 2:
        return np.full(returns.shape[1:], np.nan)
    std = returns.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(std > 0.0, returns.mean(axis=0) / std, np.nan)


def best_column(returns: np.ndarray) -> int | None:
    """The column with the highest Sharpe, ties to the earlier one; None when none is defined."""
    sharpe = _sharpe(returns)
    if np.isnan(sharpe).all():
        return None
    return int(np.nanargmax(sharpe))


class CpcvResult(BaseModel):
    groups: int
    test_groups: int
    purge: int
    embargo: int
    n_splits: int
    n_paths: int
    path_sharpes: list[float | None]  # annualized, in path order; None without variance
    choices: list[str | None]  # the value each split chose; None when none had a Sharpe
    choice_shares: dict[str, float]  # share of splits choosing each value, grid order
    mean_sharpe: float | None
    median_sharpe: float | None
    min_sharpe: float | None
    max_sharpe: float | None
    positive_share: float | None  # of the paths with a defined Sharpe

    @property
    def defined_paths(self) -> int:
        return sum(1 for sharpe in self.path_sharpes if sharpe is not None)


CPCV_GATE_RULE = (
    "median Sharpe of the CPCV paths > 0; inconclusive if fewer than half the paths "
    "have a defined Sharpe"
)


def cpcv_gate(result: CpcvResult) -> bool | None:
    """The in-sample gate of a hypothesis frozen with `cpcv` (REQ-830)."""
    if result.defined_paths * 2 < result.n_paths or result.median_sharpe is None:
        return None
    return result.median_sharpe > 0.0


def cpcv_of_selection(
    returns: np.ndarray, labels: list[str], settings: CpcvSettings, periods_per_year: int
) -> CpcvResult:
    """CPCV of choosing, on each training set, the grid value with the best Sharpe
    (REQ-813, REQ-814). `returns` is T x K: net daily returns of the K grid values
    over the training period, columns in grid order as `labels`. A split whose
    training set gives no value a Sharpe holds nothing in its test periods.
    """
    matrix = np.asarray(returns, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != len(labels):
        raise ValueError("returns must be T x K with one label per column")
    n_periods = len(matrix)
    embargo = settings.embargo(n_periods)
    splits = cpcv_splits(
        n_periods, settings.groups, settings.test_groups, settings.purge_days, embargo
    )
    chosen = [best_column(matrix[split.train]) for split in splits]

    bounds = group_bounds(n_periods, settings.groups)
    path_sharpes: list[float | None] = []
    for path in cpcv_paths(settings.groups, settings.test_groups):
        series = np.zeros(n_periods)
        for group, split_index in enumerate(path):
            start, end = bounds[group]
            column = chosen[split_index]
            if column is not None:
                series[start:end] = matrix[start:end, column]
        sharpe = _sharpe(series[:, None])[0]
        path_sharpes.append(None if np.isnan(sharpe) else float(sharpe * np.sqrt(periods_per_year)))

    defined = [sharpe for sharpe in path_sharpes if sharpe is not None]
    return CpcvResult(
        groups=settings.groups,
        test_groups=settings.test_groups,
        purge=settings.purge_days,
        embargo=embargo,
        n_splits=len(splits),
        n_paths=len(path_sharpes),
        path_sharpes=path_sharpes,
        choices=[None if column is None else labels[column] for column in chosen],
        choice_shares={
            label: sum(1 for column in chosen if column == index) / len(splits)
            for index, label in enumerate(labels)
        },
        mean_sharpe=float(np.mean(defined)) if defined else None,
        median_sharpe=float(np.median(defined)) if defined else None,
        min_sharpe=min(defined) if defined else None,
        max_sharpe=max(defined) if defined else None,
        positive_share=sum(1 for sharpe in defined if sharpe > 0) / len(defined)
        if defined
        else None,
    )
