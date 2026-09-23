from datetime import date

from quantlab.core.data.provider import PriceBar


class ZeroCostModel:
    name = "zero-cost"

    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float:
        return 0.0
