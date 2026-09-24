from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Universe
from quantlab.strategy.base import Strategy
from quantlab.strategy.signal import Signal


class MembersOnly:
    """A strategy that sees only the universe's members on the signal date (REQ-503).

    The runner wraps every strategy in it, so no strategy can rank, trade or
    even look at an instrument that was not in the universe that day. With a
    static universe the inner strategy receives the very same bars, so results
    are unchanged to the bit.
    """

    def __init__(self, strategy: Strategy, universe: Universe) -> None:
        self.strategy = strategy
        self.universe = universe

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        if self.universe.is_static:
            return self.strategy.generate_signals(bars, as_of)
        members = self.universe.members(as_of)
        visible = {
            instrument_id: bars[instrument_id] for instrument_id in bars if instrument_id in members
        }
        return self.strategy.generate_signals(visible, as_of)
