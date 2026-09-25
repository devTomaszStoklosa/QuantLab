"""How much of a portfolio each sleeve gets (q9, REQ-901..905).

A sleeve is one frozen hypothesis traded on its own. Every rule here maps the
sleeves' daily net returns before a rebalance day to weights that are
non-negative and sum to 1 over the eligible sleeves; the rules differ only in
what they equalize - capital (equal weight), volatility (inverse volatility)
or contribution to the portfolio's variance (risk parity, Maillard, Roncalli
and Teiletche 2010).
"""

from typing import Protocol

import numpy as np


def eligible_sleeves(history: np.ndarray, window: int, min_days: int) -> np.ndarray:
    """Which sleeves may get a weight: at least `min_days` daily returns since their
    first non-zero one, and a non-zero variance over the last `window` returns.

    `history` is T x K, each sleeve's net daily returns from the anchor to the
    day before the rebalance. A day without a position returns exactly 0, so a
    sleeve that has not traded yet is not eligible, while one that trades and
    is flat for a while (a pair out of its spread trade) stays eligible.
    """
    periods = history.shape[0]
    if periods == 0:
        return np.zeros(history.shape[1], dtype=bool)  # no history before the anchor
    active = history != 0.0
    first = np.where(active.any(axis=0), active.argmax(axis=0), periods)
    recent = history[-window:]
    varies = (
        recent.var(axis=0, ddof=1) > 0.0
        if len(recent) >= 2
        else np.zeros(history.shape[1], dtype=bool)
    )
    return (periods - first >= min_days) & varies


class AllocationRule(Protocol):
    """Weights of the sleeves from their returns over the estimation window."""

    def weights(self, window: np.ndarray, eligible: np.ndarray) -> np.ndarray:
        """`window` is T x K net daily returns, `eligible` K booleans; the result is
        K weights, 0 for the sleeves that are not eligible, summing to 1 over the
        others (all 0 when none is eligible)."""
        ...


def _spread(values: np.ndarray, eligible: np.ndarray) -> np.ndarray:
    """Place the eligible sleeves' weights, normalized, among K zeros."""
    weights = np.zeros(len(eligible))
    weights[eligible] = values / values.sum()
    return weights


class EqualWeight:
    """1/K' to each of the K' eligible sleeves (REQ-902)."""

    def weights(self, window: np.ndarray, eligible: np.ndarray) -> np.ndarray:
        if not eligible.any():
            return np.zeros(len(eligible))
        return _spread(np.ones(int(eligible.sum())), eligible)


class InverseVolatility:
    """Weights proportional to 1/sigma of each eligible sleeve's window returns (REQ-903)."""

    def weights(self, window: np.ndarray, eligible: np.ndarray) -> np.ndarray:
        if not eligible.any():
            return np.zeros(len(eligible))
        return _spread(1.0 / window[:, eligible].std(axis=0, ddof=1), eligible)


class RiskParityDidNotConvergeError(ValueError):
    pass


class RiskParity:
    """Equal risk contributions w_i (Sigma w)_i among the eligible sleeves (REQ-904).

    Long-only equal risk contribution by cyclical coordinate descent (Griveau-
    Billion, Richard and Roncalli 2013): each step solves the quadratic in y_i
    of Sigma y = b / y, b equal budgets, then w = y / sum(y). With uncorrelated
    sleeves one sweep gives the inverse-volatility weights; with two sleeves
    the answer is inverse volatility whatever their correlation.
    """

    def __init__(self, tolerance: float = 1e-12, max_sweeps: int = 10_000) -> None:
        self.tolerance = tolerance
        self.max_sweeps = max_sweeps

    def weights(self, window: np.ndarray, eligible: np.ndarray) -> np.ndarray:
        if not eligible.any():
            return np.zeros(len(eligible))
        covariance = np.atleast_2d(np.cov(window[:, eligible], rowvar=False))
        return _spread(self._solve(covariance), eligible)

    def _solve(self, covariance: np.ndarray) -> np.ndarray:
        count = len(covariance)
        budget = 1.0 / count
        diagonal = np.diag(covariance)
        y = 1.0 / np.sqrt(diagonal)
        for _ in range(self.max_sweeps):
            previous = y.copy()
            for i in range(count):
                others = covariance[i] @ y - diagonal[i] * y[i]
                y[i] = (-others + np.sqrt(others**2 + 4.0 * diagonal[i] * budget)) / (
                    2.0 * diagonal[i]
                )
            if np.max(np.abs(y - previous) / y) < self.tolerance:
                return y
        contributions = y * (covariance @ y)
        raise RiskParityDidNotConvergeError(
            f"Risk parity did not converge in {self.max_sweeps} sweeps; risk contributions "
            f"range {contributions.min():.3e}..{contributions.max():.3e}"
        )


ALLOCATION_RULES: dict[str, AllocationRule] = {
    "equal_weight": EqualWeight(),
    "inverse_volatility": InverseVolatility(),
    "risk_parity": RiskParity(),
}


def risk_contributions(weights: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    """Each sleeve's share of the portfolio variance: w_i (Sigma w)_i / w'Sigma w."""
    marginal = covariance @ weights
    return weights * marginal / (weights @ marginal)


def diversification_ratio(weights: np.ndarray, covariance: np.ndarray) -> float | None:
    """(sum w_i sigma_i) / sqrt(w'Sigma w): 1 without diversification, higher the less
    the sleeves move together; None when the portfolio has no variance."""
    variance = weights @ covariance @ weights
    if variance <= 0.0:
        return None
    return float(weights @ np.sqrt(np.diag(covariance)) / np.sqrt(variance))
