"""Whether a source's prices under a ticker are the index member's (#104).

Tiingo files one company under each ticker, usually the last one to use it, with
that company's whole price history. A former S&P 500 member whose ticker another
company took over gets the newcomer's prices, which look plausible, so neither the
coverage report nor the data checks see it. The audit puts side by side the names
the index gave the member and what the source files under its ticker (name, first
and last price date), and flags every mismatch for a review. It decides nothing: a
renamed company differs by name too, and a source's name can disagree with its own
description.
"""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Protocol

from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe

# Words that say what kind of entity a company is, not which one.
_LEGAL_FORMS = frozenset(
    {
        "ag",
        "and",
        "class",
        "co",
        "companies",
        "company",
        "corp",
        "corporation",
        "del",
        "group",
        "holding",
        "holdings",
        "inc",
        "incorporated",
        "limited",
        "llc",
        "lp",
        "ltd",
        "nv",
        "of",
        "plc",
        "sa",
        "the",
    }
)
# How long before the last member day a source's last price may fall: an acquired
# company's last session can precede the removal from the index by a weekend.
_LAST_PRICE_SLACK = timedelta(days=7)


@dataclass(frozen=True)
class Listing:
    """What a source files under a ticker: the company's name, its first and last price
    dates, and its description."""

    name: str
    start: date | None
    end: date | None
    description: str = ""


class ListingSource(Protocol):
    def listing(self, instrument: Instrument) -> Listing | None:
        """What the source files under the instrument's symbol; None when it does not
        know the ticker."""
        ...


def name_words(name: str) -> frozenset[str]:
    """The words of a company name that tell which company it is: lower case, without
    punctuation or legal forms ("El Paso Corp." -> {"el", "paso"})."""
    return frozenset(re.findall(r"[a-z0-9]+", name.lower())) - _LEGAL_FORMS


def name_similarity(first: str, second: str) -> float:
    """The words two names share over all their words (Jaccard), 0.0 when either has none."""
    words, other = name_words(first), name_words(second)
    if not words or not other:
        return 0.0
    return len(words & other) / len(words | other)


def former_members(universe: Universe, start: date, end: date) -> list[Instrument]:
    """The instruments that are members on some day of [start, end] and are not members
    any more: the ones whose ticker another company may have taken over since."""
    current = {span.instrument_id for span in universe.memberships if span.end is None}
    return [
        instrument
        for instrument in universe.instruments_between(start, end)
        if instrument.id not in current and instrument.id != universe.market_proxy
    ]


def member_spans(
    universe: Universe, instrument_id: str, start: date, end: date
) -> list[Membership]:
    """The instrument's membership periods in [start, end], cut to it."""
    return [
        span.model_copy(
            update={
                "start": max(span.start, start),
                "end": end if span.end is None else min(span.end, end),
            }
        )
        for span in universe.memberships
        if span.instrument_id == instrument_id and span.overlaps(start, end)
    ]


def member_medians(
    bars: list[PriceBar], spans: list[Membership]
) -> tuple[float | None, float | None]:
    """The median raw close and the median dollar volume of the bars on member days."""
    member_bars = [bar for bar in bars if any(span.covers(bar.ts) for span in spans)]
    if not member_bars:
        return None, None
    return (
        median(bar.raw_close for bar in member_bars),
        median(bar.raw_close * bar.volume for bar in member_bars),
    )


@dataclass(frozen=True)
class TickerAudit:
    """One former member's identity check: what the index called it and when it was a
    member, what the source files under its ticker, and its prices while a member."""

    instrument: Instrument
    index_names: tuple[str, ...]
    first_member_day: date
    last_member_day: date
    listing: Listing | None
    median_close: float | None = None
    median_dollar_volume: float | None = None
    not_in_source: bool = False  # excluded already

    @property
    def similarity(self) -> float | None:
        """How close the source's name is to the closest of the index's names."""
        if self.listing is None or not self.index_names:
            return None
        return max(name_similarity(name, self.listing.name) for name in self.index_names)

    @property
    def flags(self) -> list[str]:
        """What to review; none when the source's name and dates fit the member."""
        listing = self.listing
        if listing is None:
            return ["unknown to the source"]
        flags = []
        similarity = self.similarity
        if similarity is None:
            flags.append("no name in the index's table")
        elif similarity == 0.0:
            flags.append("name differs")
        elif similarity < 1.0:
            flags.append("name partly differs")
        if listing.start is not None and listing.start > self.first_member_day:
            flags.append("prices start after membership")
        if listing.end is not None and listing.end < self.last_member_day - _LAST_PRICE_SLACK:
            flags.append("prices end before membership")
        return flags


def review_order(audits: list[TickerAudit]) -> list[TickerAudit]:
    """Flagged tickers first, the least similar names first among them; then the rest."""
    return sorted(
        audits,
        key=lambda audit: (
            not audit.flags,
            -1.0 if audit.similarity is None else audit.similarity,
            audit.instrument.symbol,
        ),
    )
