from collections.abc import Callable
from datetime import date
from fractions import Fraction
from itertools import groupby

from pydantic import BaseModel

from quantlab.backtest.run import BacktestRun
from quantlab.reporting.metrics import cagr, max_drawdown, sharpe
from quantlab.validation.base import ValidationResult

# Pass rule, pre-registered (agreed with Tomasz and committed) before any
# per-window result was computed.
MIN_POSITIVE_WINDOW_FRACTION = Fraction(2, 3)
MIN_WINDOWS_WITH_SHARPE = 3
PASS_RULE = (
    "Sharpe > 0 in at least 2/3 of windows with a defined Sharpe, and aggregate "
    "Sharpe > 0; inconclusive if fewer than 3 windows have a defined Sharpe"
)


class WindowMetrics(BaseModel):
    start: date
    end: date
    partial: bool
    cagr: float | None
    sharpe: float | None
    max_drawdown: float | None


def _defined(metric: Callable[[], float]) -> float | None:
    try:
        return metric()
    except ValueError:
        return None


def _window_metrics(
    equity: list[float], start: date, end: date, partial: bool, periods_per_year: int
) -> WindowMetrics:
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    return WindowMetrics(
        start=start,
        end=end,
        partial=partial,
        cagr=_defined(lambda: cagr(equity, periods_per_year)),
        sharpe=_defined(lambda: sharpe(returns, periods_per_year)),
        max_drawdown=_defined(lambda: max_drawdown(equity)),
    )


class WalkForwardValidator:
    """Performance per non-overlapping calendar-year window (REQ-040).

    The strategy's only parameter comes from the literature rather than being
    fitted to this data, so there is nothing to re-fit between windows: every
    window is already out-of-sample for that choice, and walk-forward reduces to
    checking whether performance holds up year by year, not just on average.

    Windows start at the first held position, so the warm-up (no signal yet)
    is not counted. Each window's first return is measured from the previous
    day's equity, so no day is lost at a boundary. A metric that is undefined
    in a window (e.g. zero variance) is recorded as None.
    """

    def __init__(self, periods_per_year: int) -> None:
        self.periods_per_year = periods_per_year

    def validate(self, run: BacktestRun) -> ValidationResult:
        snapshots = run.snapshots
        # A snapshot's positions were held over the day ending at its ts, so the
        # first snapshot (no previous day to measure from) can't start a window.
        first = next((i for i in range(1, len(snapshots)) if snapshots[i].positions), None)
        if first is None:
            return ValidationResult(
                method="walk_forward",
                passed=None,
                detail={"rule": PASS_RULE, "windows": [], "aggregate": None},
            )

        windows = []
        for year, group in groupby(range(first, len(snapshots)), key=lambda i: snapshots[i].ts.year):
            indices = list(group)
            window_start, window_end = snapshots[indices[0]].ts, snapshots[indices[-1]].ts
            equity = [snapshots[indices[0] - 1].equity] + [snapshots[i].equity for i in indices]
            partial = window_start != date(year, 1, 1) or window_end != date(year, 12, 31)
            windows.append(
                _window_metrics(equity, window_start, window_end, partial, self.periods_per_year)
            )

        aggregate = _window_metrics(
            [snapshot.equity for snapshot in snapshots[first - 1 :]],
            snapshots[first].ts,
            snapshots[-1].ts,
            False,
            self.periods_per_year,
        )

        sharpes = [window.sharpe for window in windows if window.sharpe is not None]
        positive = sum(1 for value in sharpes if value > 0)
        if len(sharpes) < MIN_WINDOWS_WITH_SHARPE:
            passed = None
        else:
            passed = (
                Fraction(positive, len(sharpes)) >= MIN_POSITIVE_WINDOW_FRACTION
                and aggregate.sharpe is not None
                and aggregate.sharpe > 0
            )

        return ValidationResult(
            method="walk_forward",
            passed=passed,
            detail={
                "rule": PASS_RULE,
                "windows": [window.model_dump(mode="json") for window in windows],
                "aggregate": aggregate.model_dump(mode="json"),
                "positive_windows": positive,
                "windows_with_sharpe": len(sharpes),
            },
        )
