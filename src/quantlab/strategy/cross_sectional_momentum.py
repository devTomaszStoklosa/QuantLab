"""Cross-sectional momentum: rank the universe on past returns, long the winners (q5)."""

from bisect import bisect_right
from calendar import monthrange
from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.signal import Signal


def _shift(year: int, month: int, months: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) - months
    return index // 12, index % 12 + 1


def month_end_bar(bars: list[PriceBar], year: int, month: int) -> PriceBar | None:
    """The instrument's last bar in the calendar month, or None if it did not trade then.

    `bars` must be sorted by date, as providers and the data layer return them;
    a binary search keeps a daily call cheap on hundreds of instruments.
    """
    last_day = date(year, month, monthrange(year, month)[1])
    index = bisect_right(bars, last_day, key=lambda bar: bar.ts) - 1
    if index < 0 or bars[index].ts < date(year, month, 1):
        return None
    return bars[index]


class CrossSectionalMomentum:
    """Jegadeesh and Titman (1993) momentum, ranked across the universe (REQ-540..543).

    On a date in month m, each instrument's momentum is its return from the last
    close of month m-1-formation_months to the last close of month m-1-skip_months
    (adjusted closes: returns, not price levels). An instrument enters the ranking
    if it trades at both ends of that window and its quoted (raw) close at the end
    of month m-1 is at least `min_price`. The portfolio is long the top
    floor(n * quantile) and, when `long_short`, short as many at the bottom; ties
    go to the lower instrument id. With fewer than one instrument per leg there is
    no position.

    Everything is known at the end of month m-1, so the portfolio is formed on the
    first trading day of month m and the signals stay the same through the month;
    only the universe's membership (MembersOnly) can change them earlier. The
    ranking is computed once per month and set of instruments seen, since the
    engines call the strategy every day.
    """

    def __init__(
        self,
        formation_months: int,
        skip_months: int,
        quantile: float,
        long_short: bool,
        min_price: float,
    ) -> None:
        if not 0 <= skip_months < formation_months:
            raise ValueError("skip_months must be at least 0 and below formation_months")
        if not 0 < quantile <= 0.5:
            raise ValueError("quantile must be in (0, 0.5]")
        self.formation_months = formation_months
        self.skip_months = skip_months
        self.quantile = quantile
        self.long_short = long_short
        self.min_price = min_price
        self._portfolios: dict[tuple[int, int, frozenset[str]], list[tuple[str, str, float]]] = {}

    def momentum(self, bars: list[PriceBar], year: int, month: int) -> float | None:
        """The instrument's momentum for a portfolio held in (year, month), or None if it
        cannot enter the ranking then."""
        formed = month_end_bar(bars, *_shift(year, month, 1))
        start = month_end_bar(bars, *_shift(year, month, 1 + self.formation_months))
        end = month_end_bar(bars, *_shift(year, month, 1 + self.skip_months))
        if formed is None or start is None or end is None or formed.raw_close < self.min_price:
            return None
        return end.close / start.close - 1.0

    def _portfolio(
        self, bars: dict[str, list[PriceBar]], year: int, month: int
    ) -> list[tuple[str, str, float]]:
        ranked = sorted(
            (
                (value, instrument_id)
                for instrument_id, instrument_bars in bars.items()
                if (value := self.momentum(instrument_bars, year, month)) is not None
            ),
            key=lambda item: (-item[0], item[1]),
        )
        per_leg = int(len(ranked) * self.quantile)
        if per_leg < 1:
            return []
        legs = [(instrument_id, "long", value) for value, instrument_id in ranked[:per_leg]]
        if self.long_short:
            losers = sorted(ranked, key=lambda item: (item[0], item[1]))[:per_leg]
            legs += [(instrument_id, "short", value) for value, instrument_id in losers]
        return sorted(legs)

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        key = (as_of.year, as_of.month, frozenset(bars))
        if key not in self._portfolios:
            self._portfolios[key] = self._portfolio(bars, as_of.year, as_of.month)
        return [
            Signal(instrument_id=instrument_id, ts=as_of, direction=direction, strength=value)
            for instrument_id, direction, value in self._portfolios[key]
        ]
