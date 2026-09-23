from datetime import date
from typing import Literal

from pydantic import BaseModel


class Signal(BaseModel):
    instrument_id: str
    ts: date
    direction: Literal["long", "short", "flat"]
    strength: float
