import math
from typing import Protocol

from quantlab.core.data.provider import PriceBar


class FillPolicy(Protocol):
    """How much of an order the market absorbs on its fill bar.

    Returns a quantity with the order's sign and no larger than the order.
    """

    def fillable(self, quantity: float, bar: PriceBar) -> float: ...


class FullFill:
    """Every order fills completely, as the vectorized engine assumes."""

    def fillable(self, quantity: float, bar: PriceBar) -> float:
        return quantity


class VolumeParticipationFill:
    """At most `max_participation` of the fill bar's volume, in instrument units (REQ-230).

    The rest of the order is not filled; the execution model does not carry
    it over, so the next rebalance re-targets from what is actually held.
    """

    def __init__(self, max_participation: float) -> None:
        if not 0.0 < max_participation <= 1.0:
            raise ValueError("max_participation must be in (0, 1]")
        self.max_participation = max_participation

    def fillable(self, quantity: float, bar: PriceBar) -> float:
        limit = self.max_participation * bar.volume
        if abs(quantity) <= limit:
            return quantity
        return math.copysign(limit, quantity)
