from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.signal import Signal, signals_for_universe, trailing_return


def compute_reversal_signal(
    bars: list[PriceBar], as_of: date, formation_days: int
) -> Signal | None:
    """Short-term reversal (Jegadeesh 1990, Lehmann 1990): bet that the last
    `formation_days` move partly undoes itself - short after a rise, long after
    a fall, flat after an exactly zero return (REQ-311).

    Pure function of price history and the formation period, using only bars
    with ts <= as_of (REQ-310). `strength` is the raw formation-period return,
    as for momentum; the engine weights by direction only. None when there is
    not enough history yet, or no bar for as_of itself.
    """
    formation_return = trailing_return(bars, as_of, formation_days)
    if formation_return is None:
        return None

    if formation_return > 0:
        direction = "short"
    elif formation_return < 0:
        direction = "long"
    else:
        direction = "flat"

    return Signal(
        instrument_id=bars[0].instrument_id,
        ts=as_of,
        direction=direction,
        strength=formation_return,
    )


class ShortTermReversal:
    """`Strategy` implementation wrapping `compute_reversal_signal` for a universe."""

    def __init__(self, formation_days: int) -> None:
        self.formation_days = formation_days

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        return signals_for_universe(
            bars,
            as_of,
            lambda instrument_bars, day: compute_reversal_signal(
                instrument_bars, day, self.formation_days
            ),
        )
