from collections.abc import Callable
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from quantlab.core.data.provider import PriceBar


class Signal(BaseModel):
    instrument_id: str
    ts: date
    direction: Literal["long", "short", "flat"]
    strength: float
    # Target weight magnitude for sizers that use it (REQ-410); the direction
    # gives its sign. Strategies sized equally by sign leave it unset.
    weight: float | None = Field(default=None, gt=0)


def trailing_return(bars: list[PriceBar], as_of: date, days: int) -> float | None:
    """Close-to-close return over the last `days` bars up to and including as_of.

    Only bars with ts <= as_of are used (REQ-010, no look-ahead): any bar dated
    after as_of in the input is ignored, not just unused by chance. None when
    there is no bar for as_of itself or fewer than `days` bars before it.
    """
    history = sorted((bar for bar in bars if bar.ts <= as_of), key=lambda bar: bar.ts)
    if not history or history[-1].ts != as_of or len(history) <= days:
        return None
    past = history[-1 - days]
    return (history[-1].close - past.close) / past.close


def signals_for_universe(
    bars: dict[str, list[PriceBar]],
    as_of: date,
    compute: Callable[[list[PriceBar], date], Signal | None],
) -> list[Signal]:
    """One signal per instrument that has one; an instrument with too little
    history is skipped rather than failing the whole universe.
    """
    signals = []
    for instrument_id in sorted(bars):
        signal = compute(bars[instrument_id], as_of)
        if signal is not None:
            signals.append(signal)
    return signals
