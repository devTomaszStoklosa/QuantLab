"""A portfolio of sleeves traded as net positions (q9, REQ-910..914).

Each sleeve is a frozen hypothesis: its strategy, its sizer, its rebalance
policy and its cost model. Once a month the sleeves get weights from a frozen
allocation rule applied to their recent daily net returns; every day each
sleeve's own sizer turns its signals into target weights, and the portfolio
holds their weighted sum per instrument. To the engines the portfolio is one
strategy whose signals carry those net weights (sized by `CarriedWeights`), so
opposite positions of two sleeves offset before any order, and only changes of
the net positions are traded and costed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from pydantic import BaseModel

from quantlab.backtest.rebalance import RebalancePolicy
from quantlab.backtest.sizing import Sizer
from quantlab.core.data.provider import PriceBar, count_through
from quantlab.costs.base import CostModel
from quantlab.portfolio.allocation import AllocationRule, diversification_ratio, eligible_sleeves
from quantlab.strategy.base import Strategy
from quantlab.strategy.selected_parameter import net_returns
from quantlab.strategy.signal import Signal


@dataclass(frozen=True)
class Sleeve:
    """One component of the portfolio, as its own definition trades it."""

    name: str
    build: Callable[[], Strategy]
    sizer: Sizer
    rebalance: RebalancePolicy
    cost_model: CostModel


class SleeveHistory:
    """Each sleeve's daily net returns before a rebalance day, from a standalone
    run anchored at `history_start` on bars dated before that day only (REQ-913).

    The runs do not depend on the allocation rule or on the portfolio's cost
    model, so every portfolio built from the same sleeves can share one history.
    Its memo is keyed by the day and by the bars before it, not by the day
    alone: a run on other bars (a stress scenario) gets its own returns.
    """

    def __init__(self, sleeves: list[Sleeve], history_start: date) -> None:
        names = [sleeve.name for sleeve in sleeves]
        if len(set(names)) != len(names) or len(names) < 1:
            raise ValueError(f"Sleeves need distinct names, got {names}")
        self.sleeves = sleeves
        self.history_start = history_start
        self._strategies = {sleeve.name: sleeve.build() for sleeve in sleeves}
        self._returns: dict[tuple, np.ndarray] = {}

    @property
    def names(self) -> list[str]:
        return [sleeve.name for sleeve in self.sleeves]

    def returns(self, bars: dict[str, list[PriceBar]], day: date) -> np.ndarray:
        """T x K daily net returns from the anchor to the day before `day`, sleeves in
        order; no rows before the anchor has two trading days."""
        last = day - timedelta(days=1)
        known = {
            instrument_id: series[: count_through(series, last)]
            for instrument_id, series in bars.items()
        }
        # Bars are frozen dataclasses: equal content, equal key.
        key = (day, tuple((i, tuple(series)) for i, series in sorted(known.items())))
        if key not in self._returns:
            self._returns[key] = self._compute(known, day)
        return self._returns[key]

    def _compute(self, known: dict[str, list[PriceBar]], day: date) -> np.ndarray:
        last = day - timedelta(days=1)
        columns = []
        for sleeve in self.sleeves:
            try:
                returns = net_returns(
                    self._strategies[sleeve.name],
                    sleeve.cost_model,
                    known,
                    self.history_start,
                    last,
                    sizer=sleeve.sizer,
                    rebalance=sleeve.rebalance,
                )
            except ValueError:
                returns = []  # no trading day between the anchor and the rebalance day
            columns.append(returns)
        lengths = {len(column) for column in columns}
        if len(lengths) != 1:
            raise ValueError(f"Sleeve histories before {day} differ in length: {lengths}")
        return np.array(columns, dtype=float).T.reshape(lengths.pop(), len(columns))


class AllocationRecord(BaseModel):
    """The sleeve weights in force from one rebalance day to the next."""

    month: date  # the rebalance day: the first day of the month
    history_days: int  # daily returns each sleeve had before it
    weights: dict[str, float]  # 0 for the sleeves that were not eligible
    diversification_ratio: float | None  # None without an eligible sleeve


class StrategyPortfolio:
    """Holds each sleeve's target weights times the sleeve's weight, summed per instrument.

    On the first day of each month the frozen allocation rule weights the
    sleeves from their last `window_days` daily net returns before that day
    (`SleeveHistory`); a sleeve is eligible only `min_window_days` after its
    first non-zero return and with a non-zero variance in the window. Until a
    sleeve is eligible the portfolio holds nothing (REQ-914). Weights are
    computed once per month.
    """

    def __init__(
        self,
        history: SleeveHistory,
        rule: AllocationRule,
        window_days: int,
        min_window_days: int,
    ) -> None:
        self.history = history
        self.rule = rule
        self.window_days = window_days
        self.min_window_days = min_window_days
        self._strategies = {sleeve.name: sleeve.build() for sleeve in history.sleeves}
        self._allocations: dict[date, AllocationRecord] = {}

    @property
    def allocations(self) -> list[AllocationRecord]:
        """The allocations made so far, by month."""
        return [self._allocations[month] for month in sorted(self._allocations)]

    def allocation(self, bars: dict[str, list[PriceBar]], month: date) -> AllocationRecord:
        if month not in self._allocations:
            self._allocations[month] = self._allocate(bars, month)
        return self._allocations[month]

    def _allocate(self, bars: dict[str, list[PriceBar]], month: date) -> AllocationRecord:
        returns = self.history.returns(bars, month)
        names = self.history.names
        eligible = eligible_sleeves(returns, self.window_days, self.min_window_days)
        window = returns[-self.window_days :]
        weights = self.rule.weights(window, eligible)
        ratio = None
        if eligible.any():
            covariance = np.atleast_2d(np.cov(window[:, eligible], rowvar=False))
            ratio = diversification_ratio(weights[eligible], covariance)
        return AllocationRecord(
            month=month,
            history_days=len(returns),
            weights={name: float(weight) for name, weight in zip(names, weights, strict=True)},
            diversification_ratio=ratio,
        )

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        weights = self.allocation(bars, as_of.replace(day=1)).weights
        net: dict[str, float] = {}
        for sleeve in self.history.sleeves:
            weight = weights[sleeve.name]
            if weight == 0.0:
                continue
            signals = [
                signal
                for signal in self._strategies[sleeve.name].generate_signals(bars, as_of)
                if signal.direction != "flat" and _trades_on(bars[signal.instrument_id], as_of)
            ]
            for instrument_id, target in sleeve.sizer.weights(signals).items():
                net[instrument_id] = net.get(instrument_id, 0.0) + weight * target
        return [
            Signal(
                instrument_id=instrument_id,
                ts=as_of,
                direction="long" if value > 0.0 else "short",
                strength=abs(value),
                weight=abs(value),
            )
            for instrument_id, value in sorted(net.items())
            if value != 0.0
        ]


def _trades_on(series: list[PriceBar], as_of: date) -> bool:
    """Whether the instrument has a bar at the decision close, as the engines require."""
    known = count_through(series, as_of)
    return known > 0 and series[known - 1].ts == as_of
