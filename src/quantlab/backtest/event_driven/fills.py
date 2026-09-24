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
