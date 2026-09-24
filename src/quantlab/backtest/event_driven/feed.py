from bisect import bisect_right
from datetime import date

from quantlab.core.data.provider import PriceBar


class BarFeed:
    """Price history revealed one trading date at a time (REQ-210).

    Nothing dated after the current date can be read: history() holds only
    revealed bars and bar() only the current date's. The strategy, the
    execution model and the cost model all see the market through the feed,
    so look-ahead is ruled out by construction instead of by each of them
    filtering its input.
    """

    def __init__(self, bars: dict[str, list[PriceBar]]) -> None:
        self._bars = {
            instrument_id: sorted(instrument_bars, key=lambda bar: bar.ts)
            for instrument_id, instrument_bars in bars.items()
        }
        self._dates = {
            instrument_id: [bar.ts for bar in instrument_bars]
            for instrument_id, instrument_bars in self._bars.items()
        }
        self._revealed = dict.fromkeys(self._bars, 0)
        self._current: date | None = None

    @property
    def current(self) -> date | None:
        return self._current

    def advance(self, ts: date) -> None:
        if self._current is not None and ts <= self._current:
            raise ValueError(f"The feed only moves forward: {ts} is not after {self._current}")
        self._current = ts
        for instrument_id, dates in self._dates.items():
            self._revealed[instrument_id] = bisect_right(dates, ts)

    def history(self) -> dict[str, list[PriceBar]]:
        return {
            instrument_id: self.instrument_history(instrument_id) for instrument_id in self._bars
        }

    def instrument_history(self, instrument_id: str) -> list[PriceBar]:
        return self._bars[instrument_id][: self._revealed[instrument_id]]

    def bar(self, instrument_id: str) -> PriceBar | None:
        """The instrument's bar for the current date, or None if it has none."""
        revealed = self._revealed[instrument_id]
        if revealed and self._dates[instrument_id][revealed - 1] == self._current:
            return self._bars[instrument_id][revealed - 1]
        return None

    def trading_bar(self, instrument_id: str) -> PriceBar | None:
        """The current bar if the instrument trades on it: a delisting bar is the value
        holders received, not a market to trade in (q5, REQ-523)."""
        bar = self.bar(instrument_id)
        return None if bar is None or bar.delisting else bar

    def last_close(self, instrument_id: str) -> float | None:
        revealed = self._revealed[instrument_id]
        return self._bars[instrument_id][revealed - 1].close if revealed else None
