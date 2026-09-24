from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.reporting.contrast import return_correlation

_FIRST_DAY = date(2020, 1, 1)
_RETURNS = [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.015]


def _run(returns: list[float], held: list[bool] | None = None) -> BacktestRun:
    """Snapshot i+1 earns returns[i]; held[i] says whether it holds a position."""
    held = held if held is not None else [True] * len(returns)
    equity = np.cumprod([1.0, *(1.0 + r for r in returns)])
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_FIRST_DAY,
        end=_FIRST_DAY + timedelta(days=len(returns)),
        seed=0,
        git_sha="x",
        snapshots=[PortfolioSnapshot(ts=_FIRST_DAY, cash=1.0, positions={}, equity=1.0)]
        + [
            PortfolioSnapshot(
                ts=_FIRST_DAY + timedelta(days=i + 1),
                cash=0.0,
                positions={"a": 1.0} if is_held else {},
                equity=float(equity[i + 1]),
            )
            for i, is_held in enumerate(held)
        ],
    )


def test_identical_returns_correlate_perfectly() -> None:
    assert return_correlation(_run(_RETURNS), _run(_RETURNS)) == pytest.approx(1.0)


def test_mirrored_returns_correlate_perfectly_negatively() -> None:
    mirrored = [-r for r in _RETURNS]

    assert return_correlation(_run(_RETURNS), _run(mirrored)) == pytest.approx(-1.0)


def test_only_days_both_runs_held_a_position_count() -> None:
    held = [True, True, True, True, False, False, False]
    # Mirrored while both hold; identical on the days only one of them does.
    other = [-r for r in _RETURNS[:4]] + _RETURNS[4:]

    assert return_correlation(_run(_RETURNS), _run(other, held)) == pytest.approx(-1.0)


def test_fewer_than_two_common_days_is_undefined() -> None:
    held = [True] + [False] * 6

    assert return_correlation(_run(_RETURNS), _run(_RETURNS, held)) is None


def test_no_variance_is_undefined() -> None:
    assert return_correlation(_run(_RETURNS), _run([0.01] * len(_RETURNS))) is None
