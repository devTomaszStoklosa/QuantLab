from itertools import pairwise

import numpy as np

from quantlab.backtest.run import BacktestRun


def _held_returns(run: BacktestRun) -> dict:
    """Net return of each period in which the run held a position, by its end date."""
    return {
        current.ts: current.equity / previous.equity - 1.0
        for previous, current in pairwise(run.snapshots)
        if current.positions
    }


def return_correlation(a: BacktestRun, b: BacktestRun) -> float | None:
    """Pearson correlation of two runs' daily net returns on the days both held
    a position (REQ-340). Days on which either run was out of the market are
    left out: a flat day's zero return says nothing about how the strategies
    move together. None with fewer than 2 such days or no variance in either.
    """
    returns_a, returns_b = _held_returns(a), _held_returns(b)
    days = sorted(returns_a.keys() & returns_b.keys())
    if len(days) < 2:
        return None
    x = np.array([returns_a[day] for day in days])
    y = np.array([returns_b[day] for day in days])
    if x.std() == 0.0 or y.std() == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])
