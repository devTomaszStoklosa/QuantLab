from datetime import date
from typing import Protocol

from pydantic import BaseModel

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


class DataNotFoundError(Exception):
    def __init__(self, symbol: str) -> None:
        super().__init__(f"Unknown instrument '{symbol}'")
        self.symbol = symbol


class DataProvider(Protocol):
    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]: ...
