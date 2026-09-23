from datetime import date
from typing import Protocol

from quantlab.core.data.provider import PriceBar


class CostModel(Protocol):
    """Transaction cost for trading `traded_weight` of one instrument on `as_of`.

    Returns the cost as a fraction of portfolio equity. `instrument_bars` is
    that instrument's price history; implementations may only use bars with
    ts <= as_of (same no-look-ahead rule as strategies).
    """

    name: str

    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float: ...
