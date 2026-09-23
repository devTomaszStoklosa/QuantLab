from datetime import date

from quantlab.core.data.provider import PriceBar


class NaiveCostModel:
    """Fixed cost in basis points per unit of traded weight."""

    def __init__(self, bps: float) -> None:
        self.bps = bps
        self.name = f"naive-{bps:g}bps"

    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float:
        return self.bps / 10_000 * traded_weight
