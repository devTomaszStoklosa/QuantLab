"""Prices adjusted for corporate actions, so close-to-close returns are total returns."""

from bisect import bisect_left

from quantlab.core.data.events import CorporateAction, InstrumentEvents
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


def with_events(
    bars: dict[str, list[PriceBar]], events: dict[str, InstrumentEvents]
) -> dict[str, list[PriceBar]]:
    """Each instrument's bars with its events applied; an instrument without events keeps
    its very list of bars, so crypto results are unchanged to the bit."""
    return {
        instrument_id: adjust_bars(
            instrument_bars, events[instrument_id].actions if instrument_id in events else []
        )
        for instrument_id, instrument_bars in bars.items()
    }
