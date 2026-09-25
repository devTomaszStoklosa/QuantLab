import math
from collections.abc import Callable
from datetime import date

import numpy as np

from quantlab.core.data.provider import PriceBar, count_through
from quantlab.strategy.cointegration import engle_granger
from quantlab.strategy.signal import Signal


def spread_path(
    log_y: np.ndarray, log_x: np.ndarray, formation_days: int
) -> tuple[np.ndarray, np.ndarray]:
    """Hedge ratio and z-score of the spread on each date (REQ-421, REQ-422).

    For date i: OLS of log y on log x over the `formation_days` observations
    ending at i (inclusive), and the spread at i over the sample standard
    deviation of that window's residuals. NaN before the first full window or
    where the window has no variance. Rolling sums keep it O(n); both series
    are taken relative to their first value, so the sums stay small and
    precise.
    """
    y = np.asarray(log_y, dtype=np.float64)
    x = np.asarray(log_x, dtype=np.float64)
    n, window = len(y), formation_days
    beta = np.full(n, np.nan)
    z = np.full(n, np.nan)
    if n < window:
        return beta, z
    y, x = y - y[0], x - x[0]

    def rolling(values: np.ndarray) -> np.ndarray:
        cumulative = np.concatenate([[0.0], np.cumsum(values)])
        return cumulative[window:] - cumulative[:-window]

    sum_x, sum_y = rolling(x), rolling(y)
    centered_xx = rolling(x * x) - sum_x * sum_x / window
    centered_xy = rolling(x * y) - sum_x * sum_y / window
    centered_yy = rolling(y * y) - sum_y * sum_y / window
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(centered_xx > 0.0, centered_xy / centered_xx, np.nan)
        residual_variance = (centered_yy - slope * centered_xy) / (window - 1)
        intercept = (sum_y - slope * sum_x) / window
        last = y[window - 1 :] - intercept - slope * x[window - 1 :]
        score = np.where(residual_variance > 0.0, last / np.sqrt(residual_variance), np.nan)
    beta[window - 1 :] = slope
    z[window - 1 :] = score
    return beta, z


def pair_states(
    z: np.ndarray, entry_z: float, exit_z: float, may_enter: Callable[[int], bool]
) -> np.ndarray:
    """Spread position on each date: +1 long spread, -1 short spread, 0 flat (REQ-421).

    Flat -> short when z >= entry, flat -> long when z <= -entry, long -> flat
    when z >= -exit, short -> flat when z <= exit; an exit and an opposite
    entry can happen on the same date. `may_enter(i)` gates new positions only
    (REQ-423). An undefined z closes the position.
    """
    states = []
    state = 0
    # Plain floats: iterating a numpy array element by element is several times slower.
    for i, value in enumerate(z.tolist()):
        if math.isnan(value):
            state = 0
            states.append(0)
            continue
        if (state == 1 and value >= -exit_z) or (state == -1 and value <= exit_z):
            state = 0
        if state == 0:
            if value >= entry_z and may_enter(i):
                state = -1
            elif value <= -entry_z and may_enter(i):
                state = 1
        states.append(state)
    return np.array(states, dtype=np.int8)


class PairsSpreadReversion:
    """Pairs trading on the log spread of `dependent` against `explanatory`.

    Gatev, Goetzmann and Rouwenhorst (2006) for the formation window and the
    entry and exit thresholds; the hedge ratio is an OLS fit over the trailing
    window (Engle and Granger), so the strategy is walk-forward by
    construction. With `max_coint_p_value` set, a position opens only when the
    Engle-Granger test on that window rejects no cointegration at that level
    (Vidyamurthy 2004).

    Recomputed from the whole history up to `as_of` on every call - a pure
    function of the bars, independent of call order. Engle-Granger results
    are remembered by window content, so repeated calls do not re-test.
    Signals carry the legs' weights for PairWeights: gross exposure 1.
    """

    def __init__(
        self,
        dependent: str,
        explanatory: str,
        formation_days: int,
        entry_z: float,
        exit_z: float,
        max_coint_p_value: float | None,
    ) -> None:
        self.dependent = dependent
        self.explanatory = explanatory
        self.formation_days = formation_days
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_coint_p_value = max_coint_p_value
        self._p_values: dict[tuple[bytes, bytes], float] = {}

    def _history(self, bars: dict[str, list[PriceBar]], as_of: date):
        """Dates on which both legs have a bar up to as_of, with their log closes (REQ-420)."""
        missing = {self.dependent, self.explanatory} - bars.keys()
        if missing:
            raise ValueError(f"No price history for pair leg(s) {sorted(missing)}")
        # Bars are sorted by date (data layer): cut each leg at as_of by bisection.
        dependent = bars[self.dependent][: count_through(bars[self.dependent], as_of)]
        explanatory_bars = bars[self.explanatory][: count_through(bars[self.explanatory], as_of)]
        dates = [bar.ts for bar in dependent]
        if dates == [bar.ts for bar in explanatory_bars]:  # the usual case: same dates
            log_y = np.log(np.array([bar.close for bar in dependent], dtype=np.float64))
            log_x = np.log(np.array([bar.close for bar in explanatory_bars], dtype=np.float64))
            return dates, log_y, log_x
        explanatory = {bar.ts: bar.close for bar in explanatory_bars}
        common = sorted(
            (bar.ts, bar.close, explanatory[bar.ts]) for bar in dependent if bar.ts in explanatory
        )
        dates = [day for day, _, _ in common]
        log_y = np.log(np.array([y for _, y, _ in common], dtype=np.float64))
        log_x = np.log(np.array([x for _, _, x in common], dtype=np.float64))
        return dates, log_y, log_x

    def _cointegrated(self, log_y: np.ndarray, log_x: np.ndarray, end: int) -> bool:
        start = end - self.formation_days + 1
        window_y, window_x = log_y[start : end + 1], log_x[start : end + 1]
        key = (window_y.tobytes(), window_x.tobytes())
        if key not in self._p_values:
            try:
                self._p_values[key] = engle_granger(window_y, window_x).p_value
            except ValueError:
                self._p_values[key] = math.nan
        return self._p_values[key] < self.max_coint_p_value  # NaN never passes

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        dates, log_y, log_x = self._history(bars, as_of)
        if not dates or dates[-1] != as_of:
            return []
        beta, z = spread_path(log_y, log_x, self.formation_days)

        def may_enter(i: int) -> bool:
            return self.max_coint_p_value is None or self._cointegrated(log_y, log_x, i)

        state = int(pair_states(z, self.entry_z, self.exit_z, may_enter)[-1])
        hedge = float(beta[-1])
        if state == 0 or hedge == 0.0:
            return []
        gross = 1.0 + abs(hedge)
        y_direction = "long" if state > 0 else "short"
        x_direction = "short" if state * hedge > 0 else "long"
        return [
            Signal(
                instrument_id=self.dependent,
                ts=as_of,
                direction=y_direction,
                strength=float(z[-1]),
                weight=1.0 / gross,
            ),
            Signal(
                instrument_id=self.explanatory,
                ts=as_of,
                direction=x_direction,
                strength=float(z[-1]),
                weight=abs(hedge) / gross,
            ),
        ]
