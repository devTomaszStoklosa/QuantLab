from typing import Literal

from pydantic import BaseModel


class Instrument(BaseModel):
    id: str
    symbol: str
    asset_class: Literal["crypto"]
    quote_asset: str
