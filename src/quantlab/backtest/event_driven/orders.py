from datetime import date
from typing import Self

from pydantic import BaseModel, model_validator


class Order(BaseModel):
    """A change of held quantity, sized at the decision close (REQ-222).

    `quantity` is in instrument units (negative sells) and `decision_equity`
    is the portfolio value, in currency, it was sized from.
    """

    instrument_id: str
    decision_ts: date
    quantity: float
    decision_equity: float


class Execution(BaseModel):
    """What the execution model did with an order: filled (in part) or cancelled."""

    order: Order
    filled_quantity: float
    fill_ts: date | None
    fill_price: float | None

    @classmethod
    def cancelled(cls, order: Order) -> Self:
        return cls(order=order, filled_quantity=0.0, fill_ts=None, fill_price=None)


class OrderRecord(BaseModel):
    """One order and its outcome, as recorded by the engine (REQ-231)."""

    instrument_id: str
    decision_ts: date
    quantity: float
    decision_equity: float
    filled_quantity: float
    fill_ts: date | None
    fill_price: float | None
    cost: float  # in currency

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.quantity == 0.0:
            raise ValueError("An order must change the held quantity")
        if self.filled_quantity * self.quantity < 0 or abs(self.filled_quantity) > abs(
            self.quantity
        ):
            raise ValueError("Filled quantity must have the order's sign and not exceed it")
        if self.cost < 0:
            raise ValueError("Cost cannot be negative")
        if self.filled_quantity == 0.0:
            if self.fill_ts is not None or self.fill_price is not None:
                raise ValueError("A cancelled order has no fill date or price")
        elif self.fill_ts is None or self.fill_price is None or self.fill_price <= 0:
            raise ValueError("A filled order needs a fill date and a positive price")
        elif self.fill_ts < self.decision_ts:
            raise ValueError(f"Fill {self.fill_ts} precedes the decision {self.decision_ts}")
        return self

    @property
    def limited(self) -> bool:
        """Filled for less than ordered (in part or not at all)."""
        return abs(self.filled_quantity) < abs(self.quantity)
