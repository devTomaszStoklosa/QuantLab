"""Positions scaled to a target volatility, without leverage (q11, REQ-1110..1114).

Any strategy's non-flat signals get a scale, min(max_scale, target / annualized
ex-ante volatility), carried as the signal's weight; `ScaledEqualWeight` then
splits it equally among the instruments the engine can trade. The scaling
lives in the strategy and the sizer both engines share, so the engines need no
change and keep their parity (REQ-1113).
"""

import math
from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.risk.volatility import VolatilityEstimator
from quantlab.strategy.base import Strategy
from quantlab.strategy.signal import Signal


class VolatilityTargeted:
    """`inner`'s signals, each non-flat one scaled to `target_volatility` (annualized).

    The estimate as of the decision day reads only bars up to that day. An
    instrument without an estimate (too little history, or no variance) has no
    position that day. `max_scale` is at most 1: the engines model no financing
    cost, so a position never exceeds its equal-weight share of capital.
    """

    def __init__(
        self,
        inner: Strategy,
        estimator: VolatilityEstimator,
        target_volatility: float,
        max_scale: float,
        periods_per_year: int,
    ) -> None:
        if target_volatility <= 0:
            raise ValueError("The target volatility must be positive")
        if not 0 < max_scale <= 1:
            raise ValueError("max_scale must be in (0, 1]: the engines model no borrowing cost")
        self.inner = inner
        self.estimator = estimator
        self.target_volatility = target_volatility
        self.max_scale = max_scale
        self._annualization = math.sqrt(periods_per_year)

    def scale(self, bars: list[PriceBar], as_of: date) -> float | None:
        """The position scale of one instrument as of a day; None without an estimate."""
        sigma = self.estimator.daily_volatility(bars, as_of)
        if sigma is None or sigma == 0.0:
            return None
        return min(self.max_scale, self.target_volatility / (sigma * self._annualization))

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        scaled = []
        for signal in self.inner.generate_signals(bars, as_of):
            if signal.direction == "flat":
                scaled.append(signal)
                continue
            scale = self.scale(bars[signal.instrument_id], as_of)
            if scale is not None:
                scaled.append(signal.model_copy(update={"weight": scale}))
        return scaled
