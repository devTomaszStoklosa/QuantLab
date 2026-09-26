import importlib.resources
import math
from collections import defaultdict
from datetime import date
from itertools import pairwise
from typing import Literal, Self

import yaml
from pydantic import BaseModel, Field, PrivateAttr, model_validator

# What an instrument gives exposure to; descriptive only - the ledger groups P&L by
# it (q12, REQ-1220), and no strategy or sizer branches on it.
AssetClass = Literal["crypto", "equity", "bond", "commodity", "currency", "real_estate", "cash"]

# Sessions a year of a market that trades every calendar day.
_EVERY_DAY = 365


class Instrument(BaseModel):
    id: str
    symbol: str
    asset_class: AssetClass
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

    def overlaps(self, start: date, end: date) -> bool:
        return self.start <= end and (self.end is None or start <= self.end)


class Universe(BaseModel):
    """The instruments a hypothesis may trade, point-in-time when it has memberships.

    Without memberships the universe is static: every instrument is a member on
    every date (REQ-501). With them, an instrument is a member exactly on the
    dates one of its periods covers, so a backtest sees the universe as it was
    known then, companies that later disappeared included (survivorship bias).
    """

    name: str
    asof_date: date
    # The data provider, by the name the runner's registry knows it under (REQ-506).
    source: str
    # Trading periods in a year on this universe's market; every annualized
    # statistic of its runs uses it: 365 for crypto, 252 for US equities.
    periods_per_year: int = Field(gt=0)
    instruments: list[Instrument]
    memberships: list[Membership] = []
    # The instrument standing for the whole market: its volatility sets the
    # regimes and its worst day the stress scenario (q1). None: no such analysis.
    # In a point-in-time universe it may have no membership: then it is a
    # benchmark that no strategy sees or trades (REQ-501).
    market_proxy: str | None = None
    # The market's cash (q12, REQ-1210): a short-term Treasury bill ETF whose total
    # return is the rate cash earns. Never a member and never traded; with it, the
    # run prices every bar in units of cash, so returns are returns above it. None:
    # returns are total returns and cash earns nothing (crypto, quoted in USDT).
    cash: Instrument | None = None

    _periods: dict[str, list[Membership]] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [instrument.id for instrument in self.instruments]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"Duplicate instrument id(s) in universe '{self.name}': {duplicates}")
        if self.market_proxy is not None and self.market_proxy not in ids:
            raise ValueError(f"Market proxy {self.market_proxy} is not in universe '{self.name}'")
        if self.cash is not None:
            if self.cash.id in ids:
                raise ValueError(
                    f"Cash {self.cash.id} of universe '{self.name}' is also one of its instruments"
                )
            if self.cash.asset_class != "cash":
                raise ValueError(f"Cash {self.cash.id} of universe '{self.name}' is not class cash")
        if not self.memberships:
            return self
        periods: dict[str, list[Membership]] = defaultdict(list)
        for membership in self.memberships:
            periods[membership.instrument_id].append(membership)
        unknown = sorted(periods.keys() - set(ids))
        if unknown:
            raise ValueError(f"Memberships of instruments not in universe '{self.name}': {unknown}")
        without = sorted(set(ids) - periods.keys() - {self.market_proxy})
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

    def calendar_days(self, sessions: int) -> int:
        """Calendar days holding at least `sessions` of this market's sessions (q12, REQ-1201).

        Windows count bars, but data are fetched and windows start by date. A
        market that trades every day needs exactly that many days, so crypto's
        warm-ups are what they always were. A market closed at weekends needs 7/5
        as many days plus its holidays and unscheduled closures: 1.5 a session and
        10 days more bound that from above (a US year has had as few as 248
        sessions). Extra history costs nothing, since strategies read only the bars
        they count.
        """
        if self.periods_per_year >= _EVERY_DAY:
            return sessions
        return math.ceil(1.5 * sessions) + 10

    def members(self, as_of: date) -> set[str]:
        """Ids of the instruments that belong to the universe on `as_of`."""
        if self.is_static:
            return {instrument.id for instrument in self.instruments}
        return {
            instrument_id
            for instrument_id, spans in self._periods.items()
            if any(span.covers(as_of) for span in spans)
        }

    def instruments_between(self, start: date, end: date) -> list[Instrument]:
        """What a run over [start, end] needs (REQ-505): the instruments that are members
        on some date of the window, and the market proxy; all of them when static."""
        if self.is_static:
            return list(self.instruments)
        needed = {
            instrument_id
            for instrument_id, spans in self._periods.items()
            if any(span.overlaps(start, end) for span in spans)
        }
        return [
            instrument
            for instrument in self.instruments
            if instrument.id in needed or instrument.id == self.market_proxy
        ]

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
