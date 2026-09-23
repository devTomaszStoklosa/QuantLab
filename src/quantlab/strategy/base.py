from datetime import date
from typing import Protocol

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.signal import Signal


class Strategy(Protocol):
    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]: ...
