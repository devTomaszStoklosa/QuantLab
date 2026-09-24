import importlib.resources
from collections import defaultdict
from datetime import date
from itertools import pairwise
from typing import Literal, Self

import yaml
from pydantic import BaseModel, PrivateAttr, model_validator


class Instrument(BaseModel):
    id: str
    symbol: str
    asset_class: Literal["crypto", "equity"]
    quote_asset: str


class Membership(BaseModel):
    """A period in which an instrument belongs to its universe; `end` None = still does."""

    instrument_id: str
    start: date
    end: date | None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError(
                f"Membership of {self.instrument_id} ends {self.end} before it starts {self.start}"
            )
        return self

    def covers(self, day: date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


class Universe(BaseModel):
    """The instruments a hypothesis may trade, point-in-time when it has memberships.

    Without memberships the universe is static: every instrument is a member on
    every date (REQ-501). With them, an instrument is a member exactly on the
    dates one of its periods covers, so a backtest sees the universe as it was
    known then, companies that later disappeared included (survivorship bias).
    """

    name: str
    asof_date: date
    instruments: list[Instrument]
    memberships: list[Membership] = []
    # The instrument standing for the whole market: its volatility sets the
    # regimes and its worst day the stress scenario (q1). None: no such analysis.
    market_proxy: str | None = None

    _periods: dict[str, list[Membership]] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [instrument.id for instrument in self.instruments]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"Duplicate instrument id(s) in universe '{self.name}': {duplicates}")
        if self.market_proxy is not None and self.market_proxy not in ids:
            raise ValueError(f"Market proxy {self.market_proxy} is not in universe '{self.name}'")
        if not self.memberships:
            return self
        periods: dict[str, list[Membership]] = defaultdict(list)
        for membership in self.memberships:
            periods[membership.instrument_id].append(membership)
        unknown = sorted(periods.keys() - set(ids))
        if unknown:
            raise ValueError(f"Memberships of instruments not in universe '{self.name}': {unknown}")
        without = sorted(set(ids) - periods.keys())
        if without:
            raise ValueError(
                f"Instruments without a membership in universe '{self.name}': {without}"
            )
        for instrument_id, spans in periods.items():
            spans.sort(key=lambda span: span.start)
            for earlier, later in pairwise(spans):
                if earlier.end is None or later.start <= earlier.end:
                    raise ValueError(f"Overlapping memberships of {instrument_id} in '{self.name}'")
        self._periods = dict(periods)
        return self

    @property
    def is_static(self) -> bool:
        return not self.memberships

    def members(self, as_of: date) -> set[str]:
        """Ids of the instruments that belong to the universe on `as_of`."""
        if self.is_static:
            return {instrument.id for instrument in self.instruments}
        return {
            instrument_id
            for instrument_id, spans in self._periods.items()
            if any(span.covers(as_of) for span in spans)
        }

    @classmethod
    def load(cls, name: str) -> "Universe":
        """The universe defined in quantlab/config/universes/<name>.yaml (REQ-502)."""
        resource = importlib.resources.files("quantlab.config").joinpath(
            "universes", f"{name}.yaml"
        )
        if not resource.is_file():
            raise ValueError(f"Universe '{name}' not found")
        universe = cls.model_validate(yaml.safe_load(resource.read_text(encoding="utf-8")))
        if universe.name != name:
            raise ValueError(f"Universe file '{name}.yaml' defines '{universe.name}'")
        return universe
