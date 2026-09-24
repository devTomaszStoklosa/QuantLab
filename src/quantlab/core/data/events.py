"""What happens to an instrument besides its prices: corporate actions (q5, REQ-510)."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class Split(BaseModel):
    """`ratio` new shares per old share from `ex_date` on: 2.0 for a 2:1 split, 0.1 for 1:10."""

    kind: Literal["split"] = "split"
    instrument_id: str
    ex_date: date
    ratio: float = Field(gt=0)

    def price_factor(self, ex_close: float) -> float:
        return 1.0 / self.ratio

    def volume_factor(self) -> float:
        return self.ratio


class CashDividend(BaseModel):
    """`amount` per share, in the quote currency, paid to holders before `ex_date`."""

    kind: Literal["cash_dividend"] = "cash_dividend"
    instrument_id: str
    ex_date: date
    amount: float = Field(gt=0)

    def price_factor(self, ex_close: float) -> float:
        # C0 / (C0 + D): the close-to-close return across the ex-date becomes
        # exactly (C0 + D) / C-1 - 1, the total return (REQ-512). The common
        # 1 - D / C-1 gives C0 / (C-1 - D) - 1, off by a second-order term.
        return ex_close / (ex_close + self.amount)

    def volume_factor(self) -> float:
        return 1.0


CorporateAction = Annotated[Split | CashDividend, Field(discriminator="kind")]


class InstrumentEvents(BaseModel):
    """An instrument's corporate actions over a fetched range; none for crypto."""

    actions: list[CorporateAction] = []
