import math
from statistics import NormalDist

import numpy as np
from pydantic import BaseModel

EULER_MASCHERONI = 0.5772156649015329
_NORMAL = NormalDist()


class SharpeStatistics(BaseModel):
    """What PSR needs to know about a return series (all per period, not annualized)."""

    sharpe: float  # mean / sample standard deviation (ddof=1), as in metrics.sharpe
    n_returns: int
    skewness: float
    kurtosis: float  # non-excess: 3.0 for normal returns


def sharpe_statistics(returns: list[float]) -> SharpeStatistics | None:
    """Per-period Sharpe and the shape of the returns; None when undefined (REQ-602)."""
    values = np.asarray(returns, dtype=np.float64)
    if len(values) < 3:
        return None
    std = values.std(ddof=1)
    if std == 0.0:
        return None
    centered = values - values.mean()
    second = np.mean(centered**2)
    return SharpeStatistics(
        sharpe=float(values.mean() / std),
        n_returns=len(values),
        skewness=float(np.mean(centered**3) / second**1.5),
        kurtosis=float(np.mean(centered**4) / second**2),
    )


def probabilistic_sharpe_ratio(
    statistics: SharpeStatistics, benchmark: float = 0.0
) -> float | None:
    """Probability that the true per-period Sharpe exceeds `benchmark` (REQ-601).

    Bailey and Lopez de Prado (2012): the Sharpe estimate's standard error
    grows with negative skew and fat tails, so the same Sharpe over the same
    history is less convincing for crash-prone returns. For normal returns
    (skew 0, kurtosis 3) the denominator is Lo's (2002) sqrt(1 + SR^2 / 2).
    None when the variance term is not positive (extreme negative skew).
    """
    sharpe = statistics.sharpe
    variance = 1.0 - statistics.skewness * sharpe + (statistics.kurtosis - 1.0) / 4.0 * sharpe**2
    if variance <= 0.0:
        return None
    z = (sharpe - benchmark) * math.sqrt(statistics.n_returns - 1) / math.sqrt(variance)
    return _NORMAL.cdf(z)


def null_sharpe_variance(n_returns: int) -> float:
    """Variance of a per-period Sharpe estimate when the true Sharpe is 0 (REQ-621).

    At a true Sharpe of 0 the skew and kurtosis terms vanish, so this holds
    for non-normal returns too.
    """
    if n_returns < 2:
        raise ValueError("null_sharpe_variance needs at least 2 returns")
    return 1.0 / (n_returns - 1)


def expected_max_sharpe(n_trials: int, variance: float) -> float:
    """Expected best per-period Sharpe of `n_trials` trials with no edge (REQ-620).

    Bailey and Lopez de Prado (2014), from the expected maximum of N normals.
    One trial has nothing to pick from, so its threshold is 0.
    """
    if n_trials < 1:
        raise ValueError("n_trials must be at least 1")
    if variance < 0.0:
        raise ValueError("variance cannot be negative")
    if n_trials == 1:
        return 0.0
    return math.sqrt(variance) * (
        (1.0 - EULER_MASCHERONI) * _NORMAL.inv_cdf(1.0 - 1.0 / n_trials)
        + EULER_MASCHERONI * _NORMAL.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(statistics: SharpeStatistics, n_trials: int) -> float | None:
    """PSR against the best Sharpe `n_trials` no-edge trials would reach (REQ-622).

    The trials' Sharpe variance is the null one (1 / (T - 1)): with a handful
    of trials an empirical variance across them cannot be estimated.
    """
    threshold = expected_max_sharpe(n_trials, null_sharpe_variance(statistics.n_returns))
    return probabilistic_sharpe_ratio(statistics, threshold)
