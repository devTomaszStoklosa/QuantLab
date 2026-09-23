import importlib.resources
from datetime import date
from typing import Literal, Self

import yaml
from pydantic import BaseModel, model_validator


class Instrument(BaseModel):
    id: str
    symbol: str
    asset_class: Literal["crypto"]
    quote_asset: str


class Universe(BaseModel):
    name: str
    asof_date: date
    instruments: list[Instrument]

    @model_validator(mode="after")
    def _no_duplicate_instrument_ids(self) -> Self:
        ids = [instrument.id for instrument in self.instruments]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"Duplicate instrument id(s) in universe '{self.name}': {duplicates}")
        return self

    @classmethod
    def load(cls, name: str) -> "Universe":
        raw = (
            importlib.resources.files("quantlab.config")
            .joinpath("universe.yaml")
            .read_text(encoding="utf-8")
        )
        universe = cls.model_validate(yaml.safe_load(raw))
        if universe.name != name:
            raise ValueError(f"Universe '{name}' not found (config defines '{universe.name}')")
        return universe
