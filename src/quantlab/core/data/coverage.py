"""How much of a point-in-time universe the data source has prices for (q5, REQ-554)."""

from dataclasses import dataclass
from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Universe


@dataclass(frozen=True)
class PriceCoverage:
    member_days: int  # sessions in the window times the members on each
    priced_days: int  # of those, the ones with a bar
    without_prices: list[str]  # members in the window with no bar on any of their days

    @property
    def share(self) -> float | None:
        return self.priced_days / self.member_days if self.member_days else None


def price_coverage(
    universe: Universe, bars: dict[str, list[PriceBar]], start: date, end: date
) -> PriceCoverage:
    """Member-days with a price over member-days in [start, end]. A member the source
    lacks is invisible to every strategy, which is survivorship bias the data brings
    back in: the run reports it rather than hiding it."""
    dates = {instrument_id: {bar.ts for bar in series} for instrument_id, series in bars.items()}
    sessions = sorted({day for days in dates.values() for day in days if start <= day <= end})
    member_days = priced_days = 0
    priced: dict[str, bool] = {}
    for day in sessions:
        for instrument_id in universe.members(day):
            member_days += 1
            has_price = day in dates.get(instrument_id, ())
            priced_days += has_price
            priced[instrument_id] = priced.get(instrument_id, False) or has_price
    return PriceCoverage(
        member_days=member_days,
        priced_days=priced_days,
        without_prices=sorted(i for i, seen in priced.items() if not seen),
    )
