import math

import numpy as np
from pydantic import BaseModel
from statsmodels.tsa.stattools import coint


class EngleGranger(BaseModel):
    """Engle-Granger cointegration test of y on x, both log prices (REQ-402).

    H0 is no cointegration: a small p-value says the spread y - alpha - beta*x
    reverts to its mean. p-value and critical values are MacKinnon's (2010),
    as statsmodels computes them.
    """

    alpha: float
    beta: float
    statistic: float
    p_value: float
    critical_values: dict[str, float]
    half_life: float | None  # in periods; None when the spread does not revert
    n_observations: int


def hedge_ratio(y: np.ndarray, x: np.ndarray) -> tuple[float, float]:
    """(alpha, beta) of the OLS fit y = alpha + beta * x (REQ-401)."""
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if len(y) != len(x):
        raise ValueError("Both series need the same length")
    if len(y) < 3:
        raise ValueError("A hedge ratio needs at least 3 observations")
    x_centered = x - x.mean()
    spread_x = (x_centered**2).sum()
    if spread_x == 0.0:
        raise ValueError("The explanatory series has no variance")
    beta = float((x_centered * (y - y.mean())).sum() / spread_x)
    return float(y.mean() - beta * x.mean()), beta


def half_life(spread: np.ndarray) -> float | None:
    """Periods for a deviation of the spread to halve (REQ-403).

    From the discrete Ornstein-Uhlenbeck fit d(spread)_t = c + lambda *
    spread_{t-1}: half-life = -ln 2 / ln(1 + lambda). Undefined unless
    -1 < lambda < 0 - a spread that does not revert, or overshoots its mean
    every period, has no half-life.
    """
    values = np.asarray(spread, dtype=np.float64)
    _, reversion = hedge_ratio(np.diff(values), values[:-1])
    if not -1.0 < reversion < 0.0:
        return None
    return -math.log(2.0) / math.log(1.0 + reversion)


def engle_granger(y: np.ndarray, x: np.ndarray) -> EngleGranger:
    """Hedge ratio, cointegration test and half-life of the spread of y on x."""
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    alpha, beta = hedge_ratio(y, x)
    test = coint(y, x, trend="c")
    return EngleGranger(
        alpha=alpha,
        beta=beta,
        statistic=float(test.coint_t),
        p_value=float(test.pvalue),
        critical_values={
            level: float(value)
            for level, value in zip(("1%", "5%", "10%"), test.critical_values, strict=True)
        },
        half_life=half_life(y - alpha - beta * x),
        n_observations=len(y),
    )
