from itertools import pairwise

import numpy as np

from quantlab.backtest.run import BacktestRun
from quantlab.core.data.provider import PriceBar
from quantlab.reporting.metrics import sharpe
from quantlab.validation.base import ValidationResult

# 02-spec edge case: a permutation test on too short a series is flagged, not hidden.
MIN_ACTIVE_DAYS = 365
# Ties count as "at least as extreme": order-invariant statistics can differ from
# the actual value only by floating-point summation order.
_TIE_TOLERANCE = 1e-12


def _defined_sharpe(returns: np.ndarray, periods_per_year: int) -> float:
    try:
        return sharpe(returns, periods_per_year)
    except ValueError:
        return float("nan")


class PermutationTestValidator:
    """Monte Carlo permutation of returns against fixed positions (REQ-043).

    Keeps the positions the strategy actually held and randomly re-pairs them
    with the instruments' daily returns - one shuffled day order shared by all
    instruments, so their correlation survives. The question: are positions
    lined up with the returns that followed them better than random pairing?
    A long bias in a rising market is part of the null automatically, since
    shuffled returns keep their mean. It tests the timing of the positions
    taken, not the rule on alternative price histories.

    Statistic: annualized Sharpe of gross daily returns (costs are covered by
    the cost comparison and by the net-Sharpe half of the holdout criterion).
    p = (1 + #{shuffled >= actual}) / (1 + N), which is never zero.
    """

    def __init__(
        self,
        bars: dict[str, list[PriceBar]],
        n_permutations: int,
        alpha: float,
        periods_per_year: int,
    ) -> None:
        self.bars = bars
        self.n_permutations = n_permutations
        self.alpha = alpha
        self.periods_per_year = periods_per_year

    def validate(self, run: BacktestRun) -> ValidationResult:
        instruments = sorted(self.bars)
        closes = {i: {bar.ts: bar.close for bar in self.bars[i]} for i in instruments}

        returns, weights = [], []
        for previous, current in pairwise(run.snapshots):
            row = []
            for instrument_id in instruments:
                instrument_closes = closes[instrument_id]
                if previous.ts not in instrument_closes or current.ts not in instrument_closes:
                    raise ValueError(
                        f"Permutation test needs aligned price history: {instrument_id} has no "
                        f"bar on {previous.ts if previous.ts not in instrument_closes else current.ts}"
                    )
                row.append(instrument_closes[current.ts] / instrument_closes[previous.ts] - 1.0)
            returns.append(row)
            weights.append([current.positions.get(i, 0.0) for i in instruments])
        returns_matrix = np.array(returns, dtype=np.float64)
        weights_matrix = np.array(weights, dtype=np.float64)

        active_days = int((np.abs(weights_matrix).sum(axis=1) > 0).sum())
        detail = {
            "statistic": "annualized Sharpe of gross daily returns",
            "n_permutations": self.n_permutations,
            "seed": run.seed,
            "alpha": self.alpha,
            "active_days": active_days,
            "low_confidence": active_days < MIN_ACTIVE_DAYS,
        }

        actual = _defined_sharpe((weights_matrix * returns_matrix).sum(axis=1), self.periods_per_year)
        if np.isnan(actual):
            detail["reason"] = "actual Sharpe undefined (no variance: no positions held?)"
            return ValidationResult(method="permutation", passed=None, detail=detail)

        rng = np.random.default_rng(run.seed)
        null = np.array(
            [
                _defined_sharpe(
                    (weights_matrix * returns_matrix[rng.permutation(len(returns_matrix))]).sum(axis=1),
                    self.periods_per_year,
                )
                for _ in range(self.n_permutations)
            ]
        )
        null = null[~np.isnan(null)]
        at_least_as_extreme = int((null >= actual - _TIE_TOLERANCE).sum())
        p_value = (1 + at_least_as_extreme) / (1 + len(null))

        detail.update(
            {
                "actual": actual,
                "null_mean": float(null.mean()),
                "null_std": float(null.std(ddof=1)),
                "percentile": float((null < actual).mean()),
                "p_value": p_value,
                "n_valid": len(null),
            }
        )
        return ValidationResult(
            method="permutation",
            passed=True if p_value < self.alpha else None,
            detail=detail,
        )
