from datetime import date
from typing import Protocol

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from quantlab.core.data.provider import PriceBar

LOW = "low"
MEDIUM = "medium"
HIGH = "high"
UNDEFINED = "undefined"
VOLATILITY_REGIMES = (LOW, MEDIUM, HIGH, UNDEFINED)


class RegimeClassifier(Protocol):
    def label(self, bars: list[PriceBar], as_of: date) -> str: ...


class VolatilityTercileClassifier:
    """Realized-volatility tercile as of a day, from data up to that day only (REQ-050).

    Volatility is the sample standard deviation of the last `vol_window` daily
    returns. It is ranked against the volatilities of the last `history_days`
    days (today included): up to the 1/3 quantile is low, up to the 2/3
    quantile is medium, above it is high. A trailing rather than expanding
    history keeps the terciles relative to the recent past, so a market whose
    volatility falls over the years still spends time in all three regimes.

    The label is undefined when prices were flat (zero volatility, where a
    tercile would be arbitrary) or when there is not yet enough history.
    """

    def __init__(self, vol_window: int, history_days: int) -> None:
        self.vol_window = vol_window
        self.history_days = history_days

    def label(self, bars: list[PriceBar], as_of: date) -> str:
        closes = np.array(
            [bar.close for bar in sorted(bars, key=lambda bar: bar.ts) if bar.ts <= as_of][
                -(self.history_days + self.vol_window) :
            ],
            dtype=np.float64,
        )
        returns = closes[1:] / closes[:-1] - 1.0
        if len(returns) < self.history_days + self.vol_window - 1:
            return UNDEFINED
        volatilities = sliding_window_view(returns, self.vol_window).std(axis=1, ddof=1)
        current = volatilities[-1]
        if current == 0.0:
            return UNDEFINED
        lower, upper = np.quantile(volatilities, [1 / 3, 2 / 3])
        if current <= lower:
            return LOW
        if current <= upper:
            return MEDIUM
        return HIGH


def label_periods(
    classifier: RegimeClassifier, bars: list[PriceBar], dates: list[date]
) -> dict[date, str]:
    return {as_of: classifier.label(bars, as_of) for as_of in dates}
