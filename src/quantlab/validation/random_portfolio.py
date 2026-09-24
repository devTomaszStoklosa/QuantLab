"""Random portfolios from the same cross-section: a significance test of selection (q5)."""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from quantlab.backtest.rebalance import RebalancePolicy
from quantlab.backtest.run import BacktestRun
from quantlab.backtest.sizing import Sizer
from quantlab.core.data.provider import PriceBar
from quantlab.strategy.base import Strategy
from quantlab.validation.base import ValidationResult

# Ties count as "at least as extreme": a random portfolio equal to the actual
# one can differ from it only by floating-point summation order.
_TIE_TOLERANCE = 1e-12
# Random portfolios drawn at a time: bounds memory at a few tens of MB for
# cross-sections of hundreds of instruments.
_CHUNK = 1_000


@dataclass(frozen=True)
class _Decision:
    """A rebalance of the run: the period it trades at and what it chose from."""

    period: int  # index of the first period the new targets hold for
    columns: np.ndarray  # the cross-section, as columns of the price matrix
    weights: np.ndarray  # target weight of each, zero where the strategy chose nothing


def _period_returns(gain: np.ndarray) -> np.ndarray:
    """Returns per period of a buy-and-hold portfolio from its cumulative gain (value - 1)."""
    value = 1.0 + gain
    previous = np.concatenate([np.ones_like(value[:1]), value[:-1]], axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return value / previous - 1.0


def _sharpe(total, squares, periods: int, periods_per_year: int) -> np.ndarray:
    """Annualized Sharpe (sample std, as metrics.sharpe) from sums of returns and of their
    squares, elementwise; NaN where the variance is zero or there are under 2 periods."""
    if periods < 2:
        return np.full(np.shape(total), np.nan)
    mean = np.asarray(total, dtype=np.float64) / periods
    variance = np.maximum(squares - periods * mean**2, 0.0) / (periods - 1)
    std = np.sqrt(variance)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(std > 0.0, mean / std * np.sqrt(periods_per_year), np.nan)


class RandomPortfolioValidator:
    """Random portfolios from each decision's cross-section (REQ-564).

    Asks whether the strategy picked better instruments than chance would have,
    with everything else held fixed: the dates it rebalanced on, its target
    weights, how long it held them and how they drifted with prices. At every
    decision where the run trades to new targets, each random portfolio puts the
    same weights on instruments drawn without replacement from the decision's
    cross-section - the instruments the strategy gave any signal for (long, short
    or flat) that trade at both ends of the next period - and holds them until
    the next such decision. An instrument without a price later in the holding
    keeps its last one, a delisting value included, like cash.

    The day-shuffle test (PermutationTestValidator) asks about timing instead; a
    cross-sectional strategy with lasting differences between instruments has
    none to find (q5 02-spec, business rules).

    The validator replays the run's decisions with the same strategy, sizer and
    rebalance policy as the vectorized engine, and refuses a run whose positions
    at a decision are not those targets. Statistic: annualized Sharpe of gross
    daily returns of this buy-and-hold construction, for the actual assignment
    and each random one. p = (1 + #{random >= actual}) / (1 + N), never zero.
    Holding values follow `1 + (G - 1) w`, G the price growth since the decision,
    so N portfolios over one holding are one matrix product.
    """

    def __init__(
        self,
        bars: dict[str, list[PriceBar]],
        strategy: Strategy,
        sizer: Sizer,
        rebalance: RebalancePolicy,
        n_permutations: int,
        alpha: float,
        periods_per_year: int,
    ) -> None:
        self.bars = bars
        self.strategy = strategy
        self.sizer = sizer
        self.rebalance = rebalance
        self.n_permutations = n_permutations
        self.alpha = alpha
        self.periods_per_year = periods_per_year

    def _decisions(self, run: BacktestRun, instruments: list[str]) -> list[_Decision]:
        closes = {i: {bar.ts: bar.close for bar in self.bars[i]} for i in instruments}
        column = {instrument_id: j for j, instrument_id in enumerate(instruments)}
        decisions = []
        previous_targets: dict[str, float] | None = None
        for period, (previous, current) in enumerate(pairwise(run.snapshots)):
            signals = self.strategy.generate_signals(self.bars, previous.ts)
            tradable = [
                signal
                for signal in signals
                if previous.ts in closes[signal.instrument_id]
                and current.ts in closes[signal.instrument_id]
            ]
            targets = self.sizer.weights([s for s in tradable if s.direction != "flat"])
            if not self.rebalance.holds(previous_targets, targets):
                if current.positions != targets:
                    raise ValueError(
                        f"The run's positions from {previous.ts} are not the strategy's "
                        "targets: it was not produced by this strategy, sizer and policy"
                    )
                cross_section = sorted({signal.instrument_id for signal in tradable})
                decisions.append(
                    _Decision(
                        period=period,
                        columns=np.array([column[i] for i in cross_section], dtype=np.int64),
                        weights=np.array([targets.get(i, 0.0) for i in cross_section]),
                    )
                )
            previous_targets = targets
        return decisions

    def validate(self, run: BacktestRun) -> ValidationResult:
        instruments = sorted(self.bars)
        dates = [snapshot.ts for snapshot in run.snapshots]
        periods = len(dates) - 1
        decisions = self._decisions(run, instruments)

        closes = {i: {bar.ts: bar.close for bar in self.bars[i]} for i in instruments}
        prices = np.array(
            [[closes[i].get(day, np.nan) for i in instruments] for day in dates], dtype=np.float64
        )
        # A price that stops (a delisting, a halt) stays at its last value.
        last_seen = np.where(np.isnan(prices), 0, np.arange(len(dates))[:, None])
        held_prices = prices[np.maximum.accumulate(last_seen, axis=0), np.arange(len(instruments))]

        active_days = sum(1 for snapshot in run.snapshots[1:] if snapshot.positions)
        held = [decision for decision in decisions if decision.weights.any()]
        detail: dict = {
            "test": "random_portfolio",
            "statistic": "annualized Sharpe of gross daily returns",
            "n_permutations": self.n_permutations,
            "seed": run.seed,
            "alpha": self.alpha,
            "active_days": active_days,
            # 02-spec edge case: fewer than a year of positions is flagged, not hidden.
            "low_confidence": active_days < self.periods_per_year,
            "decisions": len(held),
            "mean_cross_section": (
                float(np.mean([len(decision.columns) for decision in held])) if held else 0.0
            ),
        }

        rng = np.random.default_rng(run.seed)
        actual = np.zeros(periods)
        total = np.zeros(self.n_permutations)
        squares = np.zeros(self.n_permutations)
        ends = [decision.period for decision in decisions[1:]] + [periods]
        for decision, end in zip(decisions, ends, strict=True):
            if not decision.weights.any():
                continue  # no position: every portfolio earns nothing
            start = decision.period
            growth = (
                held_prices[start + 1 : end + 1, decision.columns] / prices[start, decision.columns]
                - 1.0
            )
            actual[start:end] = _period_returns(growth @ decision.weights)
            size = len(decision.columns)
            for first in range(0, self.n_permutations, _CHUNK):
                count = min(_CHUNK, self.n_permutations - first)
                order = rng.permuted(np.tile(np.arange(size), (count, 1)), axis=1)
                returns = _period_returns(growth @ decision.weights[order].T)
                total[first : first + count] += returns.sum(axis=0)
                squares[first : first + count] += (returns * returns).sum(axis=0)

        observed = float(_sharpe(actual.sum(), actual @ actual, periods, self.periods_per_year))
        if np.isnan(observed):
            detail["reason"] = "actual Sharpe undefined (no variance: no positions held?)"
            return ValidationResult(method="permutation", passed=None, detail=detail)

        null = _sharpe(total, squares, periods, self.periods_per_year)
        null = null[~np.isnan(null)]
        at_least_as_extreme = int((null >= observed - _TIE_TOLERANCE).sum())
        p_value = (1 + at_least_as_extreme) / (1 + len(null))
        detail.update(
            {
                "actual": observed,
                "null_mean": float(null.mean()),
                "null_std": float(null.std(ddof=1)),
                "percentile": float((null < observed).mean()),
                "p_value": p_value,
                "n_valid": len(null),
            }
        )
        return ValidationResult(
            method="permutation", passed=True if p_value < self.alpha else None, detail=detail
        )
