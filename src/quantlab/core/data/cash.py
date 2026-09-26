"""Bars priced in units of cash, so their returns are returns above it (q12, REQ-1212).

Moskowitz, Ooi and Pedersen (2012) define time-series momentum on excess returns:
the sign of an instrument's return above cash, and positions earning that excess.
Dividing each price by a cash total-return index does both without touching the
engines: a position earns (1 + r) / (1 + r_cash) - 1, about r - r_cash; capital left
uninvested earns nothing above cash; a short earns minus the excess, its proceeds
earning the cash rate (borrow not charged); every statistic is of excess returns.
"""

from bisect import bisect_right
from dataclasses import replace

from quantlab.core.data.provider import PriceBar


def above_cash(bars: dict[str, list[PriceBar]], cash: list[PriceBar]) -> dict[str, list[PriceBar]]:
    """Each bar's open, high, low and close times C_last / C(d), with C(d) the close of
    the latest cash bar dated on or before the bar and C_last the last cash close, so
    a series ends at its market quote (REQ-1212). A bar before the first cash bar has
    no return above cash and is dropped (REQ-1213). Volume and the raw close kept for
    price-level rules (`unadjusted_close`) do not change. `cash` is sorted by date and
    adjusted for its distributions, so its closes are a total-return index.
    """
    if not cash:
        raise ValueError("No cash prices: there are no returns above cash without them")
    dates = [bar.ts for bar in cash]
    last = cash[-1].close
    priced = {}
    for instrument_id, series in bars.items():
        converted = []
        for bar in series:
            known = bisect_right(dates, bar.ts)
            if known == 0:
                continue
            factor = last / cash[known - 1].close
            converted.append(
                replace(
                    bar,
                    open=bar.open * factor,
                    high=bar.high * factor,
                    low=bar.low * factor,
                    close=bar.close * factor,
                    unadjusted_close=bar.raw_close,
                )
            )
        priced[instrument_id] = converted
    return priced
