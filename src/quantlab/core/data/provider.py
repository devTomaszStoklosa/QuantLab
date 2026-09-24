from datetime import date
from typing import Protocol

from pydantic import BaseModel

from quantlab.core.data.events import InstrumentEvents
from quantlab.core.universe import Instrument


class PriceBar(BaseModel):
    instrument_id: str
    ts: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None
    source: str
    # The raw close of a bar adjusted for corporate actions (q5, REQ-511); None
    # when the bar was never adjusted, so its close is already raw.
    unadjusted_close: float | None = None
    # The value holders received when the instrument was delisted, not a day of
    # trading (q5, REQ-521): no order fills against it and no position opens on it.
    delisting: bool = False

    @property
    def raw_close(self) -> float:
        """The close as it was quoted that day: for rules on the price level."""
        return self.close if self.unadjusted_close is None else self.unadjusted_close


class DataSourceUnavailableError(Exception):
    """The source cannot be used as configured, e.g. a missing API key or an exhausted quota."""


class DataNotFoundError(Exception):
    def __init__(self, symbol: str) -> None:
        super().__init__(f"Unknown instrument '{symbol}'")
        self.symbol = symbol


class DataProvider(Protocol):
    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]: ...

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        """Corporate actions of the instrument dated in [start, end]."""
        ...


class WithoutEvents:
    """For sources whose instruments have no corporate actions (crypto)."""

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        return InstrumentEvents()
