from datetime import date

import numpy as np
from pydantic import BaseModel

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.reporting.metrics import cagr, max_drawdown, sharpe
from quantlab.validation.base import ValidationResult


class WindowMetrics(BaseModel):
    start: date  # date of the first return in the window
    end: date  # date of the last return in the window
    periods: int
    total_return: float
    cagr: float | None  # None when the window loses everything
    sharpe: float | None  # None when returns have zero variance (e.g. never invested)
    max_drawdown: float


class WalkForwardFold(BaseModel):
    index: int
    train: WindowMetrics
    test: WindowMetrics


class WalkForwardReport(BaseModel):
    folds: list[WalkForwardFold]
    aggregate_test: WindowMetrics | None  # all test windows stitched in order
    positive_test_fraction: float | None
    unused_trailing_periods: int


def _window_metrics(dates: list[date], returns: np.ndarray, periods_per_year: int) -> WindowMetrics:
    equity = np.concatenate(([1.0], np.cumprod(1.0 + returns))).tolist()
    try:
        window_cagr = cagr(equity, periods_per_year)
    except ValueError:
        window_cagr = None
    try:
        window_sharpe = sharpe(returns.tolist(), periods_per_year)
    except ValueError:
        window_sharpe = None
    return WindowMetrics(
        start=dates[0],
        end=dates[-1],
        periods=len(returns),
        total_return=equity[-1] - 1.0,
        cagr=window_cagr,
        sharpe=window_sharpe,
        max_drawdown=max_drawdown(equity),
    )


class WalkForwardValidator:
    """Rolling walk-forward over a completed run, reported fold by fold (REQ-040).

    Periods are the run's return periods (one per snapshot after the first).
    Fold k tests `test_periods` returns starting at `train_periods + k * step_periods`
    and pairs them with the `train_periods` returns immediately before. Test
    windows never overlap when `step_periods >= test_periods` (the default), and
    a trailing stretch too short for a full test window is reported, not used.

    Nothing is refitted per fold: the strategies in this epic have parameters
    fixed a priori (e.g. a 12-month lookback from the literature), so the train
    window is what an in-sample reading looked like just before each test
    window. Setting the two side by side exposes IS -> OOS decay and whether the
    result holds up across time or rests on one lucky stretch.

    The pass rule is set in the constructor, before looking at any result:
    the stitched out-of-sample Sharpe must exceed `min_test_sharpe` and at least
    `min_positive_fraction` of test windows must have a positive Sharpe (a
    zero-variance window counts as not positive). With fewer than `min_folds`
    folds the result is inconclusive (`passed=None`), not a pass or a fail.
    """

    def __init__(
        self,
        train_periods: int,
        test_periods: int,
        periods_per_year: int,
        step_periods: int | None = None,
        min_test_sharpe: float = 0.0,
        min_positive_fraction: float = 0.5,
        min_folds: int = 3,
    ) -> None:
        step = test_periods if step_periods is None else step_periods
        if min(train_periods, test_periods, step, periods_per_year, min_folds) <= 0:
            raise ValueError("window lengths, step, periods_per_year and min_folds must be positive")
        if test_periods < 2:
            raise ValueError("test_periods must be at least 2 to compute a Sharpe ratio")
        if not 0.0 <= min_positive_fraction <= 1.0:
            raise ValueError("min_positive_fraction must be between 0 and 1")
        self.train_periods = train_periods
        self.test_periods = test_periods
        self.step_periods = step
        self.periods_per_year = periods_per_year
        self.min_test_sharpe = min_test_sharpe
        self.min_positive_fraction = min_positive_fraction
        self.min_folds = min_folds

    def report(self, run: BacktestRun) -> WalkForwardReport:
        equity = np.asarray([snapshot.equity for snapshot in run.snapshots], dtype=np.float64)
        returns = equity[1:] / equity[:-1] - 1.0
        dates = [snapshot.ts for snapshot in run.snapshots[1:]]

        folds: list[WalkForwardFold] = []
        test_start = self.train_periods
        used_until = 0
        while test_start + self.test_periods <= len(returns):
            train = slice(test_start - self.train_periods, test_start)
            test = slice(test_start, test_start + self.test_periods)
            folds.append(
                WalkForwardFold(
                    index=len(folds),
                    train=_window_metrics(dates[train], returns[train], self.periods_per_year),
                    test=_window_metrics(dates[test], returns[test], self.periods_per_year),
                )
            )
            used_until = test.stop
            test_start += self.step_periods

        if not folds:
            return WalkForwardReport(
                folds=[], aggregate_test=None, positive_test_fraction=None,
                unused_trailing_periods=len(returns),
            )

        # Overlapping test windows (step < test) would count some returns twice.
        test_indices = sorted(
            {i for fold in range(len(folds)) for i in self._test_range(fold)}
        )
        positive = sum(1 for fold in folds if fold.test.sharpe is not None and fold.test.sharpe > 0)
        return WalkForwardReport(
            folds=folds,
            aggregate_test=_window_metrics(
                [dates[i] for i in test_indices], returns[test_indices], self.periods_per_year
            ),
            positive_test_fraction=positive / len(folds),
            unused_trailing_periods=len(returns) - used_until,
        )

    def _test_range(self, fold: int) -> range:
        start = self.train_periods + fold * self.step_periods
        return range(start, start + self.test_periods)

    def validate(self, run: BacktestRun) -> ValidationResult:
        report = self.report(run)
        criterion = {
            "min_test_sharpe": self.min_test_sharpe,
            "min_positive_fraction": self.min_positive_fraction,
            "min_folds": self.min_folds,
        }
        if len(report.folds) < self.min_folds:
            passed = None
            reason = f"only {len(report.folds)} full folds, need {self.min_folds}"
        else:
            aggregate_sharpe = report.aggregate_test.sharpe
            passed = (
                aggregate_sharpe is not None
                and aggregate_sharpe > self.min_test_sharpe
                and report.positive_test_fraction >= self.min_positive_fraction
            )
            reason = "criterion met" if passed else "criterion not met"
        return ValidationResult(
            method="walk_forward",
            passed=passed,
            detail={
                "train_periods": self.train_periods,
                "test_periods": self.test_periods,
                "step_periods": self.step_periods,
                "criterion": criterion,
                "reason": reason,
                **report.model_dump(mode="json"),
            },
        )
