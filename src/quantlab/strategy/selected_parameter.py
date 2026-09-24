"""A strategy whose parameter is chosen on past data by a frozen procedure (q8, REQ-801..804)."""

from collections.abc import Callable
from datetime import date, timedelta
from itertools import pairwise

from pydantic import BaseModel

from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar, count_through
from quantlab.costs.base import CostModel
from quantlab.reporting.metrics import sharpe
from quantlab.strategy.base import Strategy
from quantlab.strategy.signal import Signal


class SelectionRecord(BaseModel):
    """One yearly choice: every grid value's Sharpe on the history before it."""

    year: int
    evaluated_from: date | None  # None: no history to evaluate on
    evaluated_to: date
    days: int  # calendar days evaluated
    sharpes: dict[str, float | None]  # per-period Sharpe of net daily returns, grid order
    chosen: str | None  # None: too little history, or no value with a Sharpe


class SelectedParameter:
    """Trades, each calendar year, the grid value that did best before it (REQ-802).

    On 1 January of year Y the choice looks only at bars dated before that day.
    Every grid value is backtested by the vectorized engine, under the
    hypothesis's cost model, over a common window: from `history_start` or from
    the first day on which every value can signal (the first bar plus the
    longest warm-up), whichever is later, to 31 December of Y-1. The value
    with the highest Sharpe of net daily returns wins, ties going to the
    earlier value in the grid; with fewer than `min_history_days` in the
    window, or no value with a Sharpe, there is no position that year.

    The chosen value's own strategy then gives the signals, so to both engines
    this is one strategy: a change of value is a change of targets, traded and
    costed like any other (REQ-803). Choices are computed once per year.
    """

    def __init__(
        self,
        variants: dict[str, Callable[[], Strategy]],
        cost_model: CostModel,
        warm_up_days: int,
        history_start: date,
        min_history_days: int,
    ) -> None:
        if len(variants) < 2:
            raise ValueError("A selection needs at least two grid values")
        self.variants = variants
        self.cost_model = cost_model
        self.warm_up_days = warm_up_days
        self.history_start = history_start
        self.min_history_days = min_history_days
        self._strategies = {label: build() for label, build in variants.items()}
        self._choices: dict[int, SelectionRecord] = {}

    @property
    def history(self) -> list[SelectionRecord]:
        """The choices made so far, by year."""
        return [self._choices[year] for year in sorted(self._choices)]

    def choice(self, bars: dict[str, list[PriceBar]], year: int) -> SelectionRecord:
        if year not in self._choices:
            self._choices[year] = self._choose(bars, year)
        return self._choices[year]

    def _choose(self, bars: dict[str, list[PriceBar]], year: int) -> SelectionRecord:
        last_day = date(year, 1, 1) - timedelta(days=1)
        known = {
            instrument_id: series[: count_through(series, last_day)]
            for instrument_id, series in bars.items()
        }
        firsts = [series[0].ts for series in known.values() if series]
        start = (
            max(self.history_start, max(firsts) + timedelta(days=self.warm_up_days))
            if firsts
            else None
        )
        days = 0 if start is None else (last_day - start).days + 1
        nothing = {label: None for label in self.variants}
        if start is None or days < self.min_history_days:
            return SelectionRecord(
                year=year,
                evaluated_from=start,
                evaluated_to=last_day,
                days=max(days, 0),
                sharpes=nothing,
                chosen=None,
            )
        sharpes = {
            label: self._sharpe(build(), known, start, last_day)
            for label, build in self.variants.items()
        }
        defined = [(value, label) for label, value in sharpes.items() if value is not None]
        best = max((value for value, _ in defined), default=None)
        chosen = next((label for value, label in defined if value == best), None)
        return SelectionRecord(
            year=year,
            evaluated_from=start,
            evaluated_to=last_day,
            days=days,
            sharpes=sharpes,
            chosen=chosen,
        )

    def _sharpe(
        self, strategy: Strategy, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> float | None:
        run = run_backtest(
            strategy=strategy,
            cost_model=self.cost_model,
            bars=bars,
            universe_name="selection",
            start=start,
            end=end,
            seed=0,
            git_sha="selection",
            strategy_name="selection",
            strategy_params={},
        )
        equity = [snapshot.equity for snapshot in run.snapshots]
        try:
            return sharpe([after / before - 1.0 for before, after in pairwise(equity)], 1)
        except ValueError:
            return None  # no variance: no position, or too few days

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        chosen = self.choice(bars, as_of.year).chosen
        if chosen is None:
            return []
        return self._strategies[chosen].generate_signals(bars, as_of)
