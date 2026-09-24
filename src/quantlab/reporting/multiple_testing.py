import math
from datetime import date
from itertools import pairwise

import numpy as np
from pydantic import BaseModel

from quantlab.backtest.run import BacktestRun
from quantlab.research.trials import Trial
from quantlab.validation.sharpe_inference import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    null_sharpe_variance,
    probabilistic_sharpe_ratio,
    sharpe_statistics,
)


def active_returns(run: BacktestRun) -> list[float]:
    """Daily net returns from the first held position on, as in walk-forward and
    regimes: a warm-up without positions would understate the variance."""
    snapshots = run.snapshots
    first = next((i for i in range(1, len(snapshots)) if snapshots[i].positions), None)
    if first is None:
        return []
    return [
        current.equity / previous.equity - 1.0
        for previous, current in pairwise(snapshots[first - 1 :])
    ]


def aligned_active_returns(runs: list[BacktestRun]) -> tuple[list[date], np.ndarray]:
    """Each run's net daily returns on the dates all of them have one, as a T x N matrix.

    A return is dated by the snapshot it ends on, and a run's returns start at
    its first held position, so the common dates begin once every run holds
    something - no strategy is compared through another's warm-up.
    """
    by_date = []
    for run in runs:
        snapshots = run.snapshots
        first = next((i for i in range(1, len(snapshots)) if snapshots[i].positions), None)
        pairs = pairwise(snapshots[first - 1 :]) if first is not None else []
        by_date.append(
            {current.ts: current.equity / previous.equity - 1.0 for previous, current in pairs}
        )
    common = sorted(set.intersection(*(set(returns) for returns in by_date))) if by_date else []
    matrix = np.array(
        [[returns[day] for returns in by_date] for day in common], dtype=np.float64
    ).reshape(len(common), len(runs))
    return common, matrix


class MultipleTesting(BaseModel):
    """PSR and DSR of a training run, with the trials they are deflated for (REQ-640).

    Descriptive: none of it enters a pass rule or a hypothesis verdict.
    """

    trials: list[str]  # hypotheses on the same data, oldest first, the run's own included
    # Parameter configurations those trials tried (q8, REQ-820): one per trial with
    # fixed parameters, the grid's size for one choosing from a grid. The DSR
    # threshold is the expected best of this many no-edge configurations.
    configurations: int
    n_returns: int
    sharpe_annualized: float | None
    psr: float | None  # probability that the true Sharpe exceeds 0
    threshold_annualized: float | None  # expected best Sharpe of that many no-edge trials
    dsr: float | None


def multiple_testing(
    run: BacktestRun, trials: list[Trial], periods_per_year: int
) -> MultipleTesting:
    if not trials:
        raise ValueError("A run is always one of its own trials")
    returns = active_returns(run)
    statistics = sharpe_statistics(returns)
    names = [trial.hypothesis for trial in trials]
    configurations = sum(trial.definition.parameters.configurations for trial in trials)
    if statistics is None:
        return MultipleTesting(
            trials=names,
            configurations=configurations,
            n_returns=len(returns),
            sharpe_annualized=None,
            psr=None,
            threshold_annualized=None,
            dsr=None,
        )
    annualize = math.sqrt(periods_per_year)
    threshold = expected_max_sharpe(configurations, null_sharpe_variance(statistics.n_returns))
    return MultipleTesting(
        trials=names,
        configurations=configurations,
        n_returns=statistics.n_returns,
        sharpe_annualized=statistics.sharpe * annualize,
        psr=probabilistic_sharpe_ratio(statistics),
        threshold_annualized=threshold * annualize,
        dsr=deflated_sharpe_ratio(statistics, configurations),
    )
