"""Bars as the engines need them: adjusted for corporate actions, ended by a delisting."""

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel

from quantlab.core.data.events import CorporateAction, Delisting, InstrumentEvents
from quantlab.core.data.provider import PriceBar


def adjust_bars(bars: list[PriceBar], actions: list[CorporateAction]) -> list[PriceBar]:
    """Back-adjusted bars: every bar before an ex-date scaled by that action's factor (REQ-511).

    Factors compound across actions; open, high, low and close take the price
    factors, volume only the split ones (shares before a 2:1 split count
    double), and `unadjusted_close` keeps each bar's raw close for rules on the
    price level. Bars on or after the last ex-date keep their prices, so the
    series ends at today's quote. An action with no bar before its ex-date or
    none on or after it adjusts nothing (REQ-513). Without actions the input
    list itself is returned, unchanged.
    """
    if not actions:
        return bars
    ordered = sorted(bars, key=lambda bar: bar.ts)
    dates = [bar.ts for bar in ordered]
    price = [1.0] * len(ordered)
    volume = [1.0] * len(ordered)
    for action in actions:
        first_after = bisect_left(dates, action.ex_date)
        if first_after == 0 or first_after == len(ordered):
            continue
        price_factor = action.price_factor(ordered[first_after].close)
        volume_factor = action.volume_factor()
        for i in range(first_after):
            price[i] *= price_factor
            volume[i] *= volume_factor
    return [
        bar.model_copy(
            update={
                "open": bar.open * price[i],
                "high": bar.high * price[i],
                "low": bar.low * price[i],
                "close": bar.close * price[i],
                "volume": bar.volume * volume[i],
                "unadjusted_close": bar.close,
            }
        )
        for i, bar in enumerate(ordered)
    ]


class AppliedDelisting(BaseModel):
    """A delisting ending an instrument's bars, and whether its return was assumed."""

    instrument_id: str
    date: date
    delisting_return: float
    assumed: bool


@dataclass(frozen=True)
class MarketData:
    """The bars a run uses, with the delistings that ended some of them (REQ-522).

    A plain dataclass, not a pydantic model: validating would copy every list of
    bars, millions of them for an equity universe.
    """

    bars: dict[str, list[PriceBar]]
    delistings: list[AppliedDelisting] = field(default_factory=list)

    @property
    def assumed_delistings(self) -> int:
        return sum(1 for delisting in self.delistings if delisting.assumed)


def delisted(
    bars: list[PriceBar], delisting: Delisting, missing_return: float | None
) -> tuple[list[PriceBar], AppliedDelisting | None]:
    """The bars ended by one bar on the delisting date, at the last close times one plus the
    delisting return, with no volume and nothing after it (REQ-521).

    An unknown return takes `missing_return`, the hypothesis's frozen assumption;
    with neither, the run cannot know what holders got and refuses. Without bars
    there is nothing to end.
    """
    if not bars:
        return bars, None
    last = max(bars, key=lambda bar: bar.ts)
    if delisting.date <= last.ts:
        raise ValueError(
            f"{delisting.instrument_id} delisted on {delisting.date} but has a bar on {last.ts}"
        )
    known = delisting.delisting_return is not None
    rate = delisting.delisting_return if known else missing_return
    if rate is None:
        raise ValueError(
            f"{delisting.instrument_id}: unknown delisting return and no "
            "missing_delisting_return in the hypothesis definition"
        )
    value = last.close * (1.0 + rate)
    final = last.model_copy(
        update={
            "ts": delisting.date,
            "open": value,
            "high": value,
            "low": value,
            "close": value,
            "volume": 0.0,
            "unadjusted_close": last.raw_close * (1.0 + rate),
            "delisting": True,
        }
    )
    applied = AppliedDelisting(
        instrument_id=delisting.instrument_id,
        date=delisting.date,
        delisting_return=rate,
        assumed=not known,
    )
    return [*sorted(bars, key=lambda bar: bar.ts), final], applied


def next_session(sessions: list[date], day: date) -> date:
    """The first of the sorted `sessions` on or after `day`; `day` itself after the last."""
    index = bisect_left(sessions, day)
    return sessions[index] if index < len(sessions) else day


def with_events(
    bars: dict[str, list[PriceBar]],
    events: dict[str, InstrumentEvents],
    missing_delisting_return: float | None = None,
) -> MarketData:
    """Each instrument's bars with its events applied: adjusted for its corporate actions,
    then ended by its delisting. An instrument without events keeps its very list of
    bars, so crypto results are unchanged to the bit.

    A source may date a delisting on the day after the last price, a weekend or a
    holiday; the delisting bar goes on the run's next session from that date, so
    it never adds a day on which no other instrument trades (REQ-521).
    """
    adjusted: dict[str, list[PriceBar]] = {}
    applied: list[AppliedDelisting] = []
    sessions: list[date] | None = None
    for instrument_id, instrument_bars in bars.items():
        instrument_events = events.get(instrument_id, InstrumentEvents())
        series = adjust_bars(instrument_bars, instrument_events.actions)
        if instrument_events.delisting is not None:
            if sessions is None:
                sessions = sorted({bar.ts for other in bars.values() for bar in other})
            source_date = instrument_events.delisting.date
            delisting = instrument_events.delisting.model_copy(
                update={"date": next_session(sessions, source_date)}
            )
            series, result = delisted(series, delisting, missing_delisting_return)
            if result is not None:
                applied.append(result)
        adjusted[instrument_id] = series
    return MarketData(bars=adjusted, delistings=applied)
