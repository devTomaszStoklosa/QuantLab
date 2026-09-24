from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.vectorized.engine import BacktestRun, PortfolioSnapshot
from quantlab.risk.conditional import regime_conditional_metrics

_FIRST_DAY = date(2020, 1, 1)


def _day(i: int) -> date:
    return _FIRST_DAY + timedelta(days=i)


def _run(equity: list[float], held: list[bool]) -> BacktestRun:
    """Snapshot i has equity[i]; held[i] says whether it holds a position."""
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_FIRST_DAY,
        end=_day(len(equity) - 1),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(
                ts=_day(i),
                cash=0.0,
                positions={"a": 1.0} if is_held else {},
                equity=value,
            )
            for i, (value, is_held) in enumerate(zip(equity, held, strict=True))
        ],
    )


def test_each_return_takes_the_regime_of_the_day_before() -> None:
    equity = [1.0, 1.01, 0.99, 1.02, 1.03]
    run = _run(equity, [False, True, True, True, True])
    labels = {_day(0): "low", _day(1): "high", _day(2): "low", _day(3): "high", _day(4): "low"}

    metrics = regime_conditional_metrics(run, labels, periods_per_year=365)

    low = [1.01 / 1.0 - 1.0, 1.02 / 0.99 - 1.0]
    high = [0.99 / 1.01 - 1.0, 1.03 / 1.02 - 1.0]
    assert set(metrics) == {"low", "high"}
    assert metrics["low"].days == 2
    assert metrics["low"].cagr == pytest.approx(((1 + low[0]) * (1 + low[1])) ** (365 / 2) - 1)
    assert metrics["low"].sharpe == pytest.approx(np.mean(low) / np.std(low, ddof=1) * np.sqrt(365))
    assert metrics["high"].sortino == pytest.approx(
        np.mean(high) / np.sqrt(np.mean(np.minimum(high, 0.0) ** 2)) * np.sqrt(365)
    )


def test_days_before_the_first_position_are_not_counted() -> None:
    run = _run([1.0, 1.0, 1.0, 1.02, 1.01], [False, False, False, True, True])
    labels = {_day(i): "low" for i in range(5)}

    metrics = regime_conditional_metrics(run, labels, periods_per_year=365)

    # The first position is held over day 2 -> day 3; the flat warm-up is left out.
    assert metrics["low"].days == 2


def test_metric_undefined_in_a_regime_is_none() -> None:
    run = _run([1.0, 1.01, 1.02, 1.03], [False, True, True, True])
    labels = {_day(0): "high", _day(1): "low", _day(2): "low", _day(3): "low"}

    metrics = regime_conditional_metrics(run, labels, periods_per_year=365)

    # A single positive day: CAGR exists, Sharpe and Sortino do not.
    assert metrics["high"].days == 1
    assert metrics["high"].cagr is not None
    assert metrics["high"].sharpe is None
    assert metrics["high"].sortino is None


def test_missing_label_raises() -> None:
    run = _run([1.0, 1.01, 1.02], [False, True, True])

    with pytest.raises(ValueError, match="No regime label"):
        regime_conditional_metrics(run, {_day(0): "low"}, periods_per_year=365)


def test_run_without_positions_has_no_regime_metrics() -> None:
    run = _run([1.0, 1.0, 1.0], [False, False, False])

    assert regime_conditional_metrics(run, {}, periods_per_year=365) == {}
