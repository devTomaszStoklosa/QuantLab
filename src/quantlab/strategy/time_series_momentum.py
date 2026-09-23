from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.signal import Signal


def compute_momentum_signal(
    bars: list[PriceBar], as_of: date, lookback_days: int
) -> Signal | None:
    """Time-series momentum (Moskowitz/Ooi/Pedersen 2012): long if the
    lookback-period return is positive, short if negative, flat if exactly zero.

    Pure function of price history and the lookback parameter (REQ-011) - no
    state between calls. Only uses bars with ts <= as_of (REQ-010, no
    look-ahead): any bar dated after as_of in the input is ignored, not just
    unused by chance.

    `strength` is the raw lookback return, not cross-sectionally normalized -
    normalization only matters for ranking across instruments, which this
    per-instrument signal doesn't do. Returns None when there isn't enough
    history yet, or no bar exists for as_of itself.
    """
    history = sorted((bar for bar in bars if bar.ts <= as_of), key=lambda bar: bar.ts)
    if not history or history[-1].ts != as_of or len(history) <= lookback_days:
        return None

    current = history[-1]
    past = history[-1 - lookback_days]
    lookback_return = (current.close - past.close) / past.close

    if lookback_return > 0:
        direction = "long"
    elif lookback_return < 0:
        direction = "short"
    else:
        direction = "flat"

    return Signal(
        instrument_id=current.instrument_id,
        ts=as_of,
        direction=direction,
        strength=lookback_return,
    )


class TimeSeriesMomentum:
    """`Strategy` implementation wrapping `compute_momentum_signal` for a universe.

    Instruments with too little history simply produce no signal for `as_of`
    (per-instrument None from the pure function) rather than failing the
    whole run - a shorter-lived instrument shouldn't block signals for the
    rest of the universe.
    """

    def __init__(self, lookback_days: int) -> None:
        self.lookback_days = lookback_days

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        signals = []
        for instrument_id in sorted(bars):
            signal = compute_momentum_signal(bars[instrument_id], as_of, self.lookback_days)
            if signal is not None:
                signals.append(signal)
        return signals
