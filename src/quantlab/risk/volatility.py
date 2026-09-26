"""Ex-ante volatility of an instrument from its own recent returns (q11, REQ-1101..1103).

Every estimator reads exactly `window_days` daily close-to-close returns up to
and including the decision day, and nothing after it. An estimate is then the
same whether a run's data starts one window or years before that day, so the
first day of a holdout sees what a run with the whole history would (REQ-1121).
"""

from datetime import date
from typing import Protocol

import numpy as np

from quantlab.core.data.provider import PriceBar, count_through


def trailing_returns(bars: list[PriceBar], as_of: date, count: int) -> np.ndarray | None:
    """The last `count` close-to-close returns up to and including as_of.

    Only bars dated on or before as_of are read (REQ-1102). None when there is
    no bar for as_of itself or fewer than `count` returns up to it. `bars` are
    sorted by date, as the data layer returns them.
    """
    known = count_through(bars, as_of)
    if known == 0 or bars[known - 1].ts != as_of or known <= count:
        return None
    closes = np.array([bar.close for bar in bars[known - count - 1 : known]], dtype=np.float64)
    return closes[1:] / closes[:-1] - 1.0


class VolatilityEstimator(Protocol):
    """A daily volatility as of a day, from the last `window_days` returns up to it."""

    window_days: int

    def daily_volatility(self, bars: list[PriceBar], as_of: date) -> float | None: ...


class RollingVolatility:
    """Sample standard deviation (ddof=1) of the last `window_days` daily returns: the
    realized volatility of Barroso and Santa-Clara (2015) and Moreira and Muir (2017)."""

    def __init__(self, window_days: int) -> None:
        if window_days < 2:
            raise ValueError("A rolling volatility needs a window of at least 2 returns")
        self.window_days = window_days

    def daily_volatility(self, bars: list[PriceBar], as_of: date) -> float | None:
        returns = trailing_returns(bars, as_of, self.window_days)
        if returns is None:
            return None
        return float(returns.std(ddof=1))


class EwmaVolatility:
    """Exponentially weighted volatility, as in Moskowitz, Ooi and Pedersen (2012).

    The i-th most recent return weighs decay**i, with decay = c / (1 + c) for a
    center of mass of c days; the weights are normalized over the window. The
    variance is taken around the exponentially weighted mean, with those same
    weights. The window is finite so that an estimate never depends on where the
    fetched data starts (the paper uses the whole history instead).
    """

    def __init__(self, center_of_mass_days: float, window_days: int) -> None:
        if center_of_mass_days <= 0:
            raise ValueError("The center of mass must be positive")
        if window_days < 2:
            raise ValueError("An EWMA volatility needs a window of at least 2 returns")
        self.center_of_mass_days = center_of_mass_days
        self.window_days = window_days
        decay = center_of_mass_days / (1.0 + center_of_mass_days)
        # Oldest return first, as trailing_returns orders them.
        weights = decay ** np.arange(window_days - 1, -1, -1, dtype=np.float64)
        self._weights = weights / weights.sum()

    def daily_volatility(self, bars: list[PriceBar], as_of: date) -> float | None:
        returns = trailing_returns(bars, as_of, self.window_days)
        if returns is None:
            return None
        mean = self._weights @ returns
        return float(np.sqrt(self._weights @ (returns - mean) ** 2))
