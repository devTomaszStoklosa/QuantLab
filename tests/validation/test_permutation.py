from datetime import date, timedelta

import pytest

from quantlab.backtest.vectorized.engine import BacktestRun, PortfolioSnapshot
from quantlab.core.data.provider import PriceBar
from quantlab.validation.permutation import PermutationTestValidator

_FIRST_DAY = date(2020, 1, 1)
# Varying magnitudes and signs so both actual and shuffled returns have variance.
_DAILY_RETURNS = [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.015, -0.005, 0.025, -0.015] * 40


def _bars(daily_returns: list[float], first_day: date = _FIRST_DAY) -> list[PriceBar]:
    closes = [100.0]
    for daily_return in daily_returns:
        closes.append(closes[-1] * (1.0 + daily_return))
    return [
        PriceBar(
            instrument_id="a",
            ts=first_day + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
            adj_close=None,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def _run(weights: list[float], seed: int = 0) -> BacktestRun:
    """Snapshot i+1 holds weights[i] over the day ending at its ts."""
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_FIRST_DAY,
        end=_FIRST_DAY + timedelta(days=len(weights)),
        seed=seed,
        git_sha="x",
        snapshots=[PortfolioSnapshot(ts=_FIRST_DAY, cash=1.0, positions={}, equity=1.0)]
        + [
            PortfolioSnapshot(
                ts=_FIRST_DAY + timedelta(days=i + 1),
                cash=0.0,
                positions={"a": weight} if weight else {},
                equity=1.0,
            )
            for i, weight in enumerate(weights)
        ],
    )


def _validator(n_permutations: int = 200) -> PermutationTestValidator:
    return PermutationTestValidator(
        bars={"a": _bars(_DAILY_RETURNS)},
        n_permutations=n_permutations,
        alpha=0.1,
        periods_per_year=365,
    )


def test_perfect_timing_gets_the_smallest_possible_p_value() -> None:
    # Long before every up day, short before every down day.
    weights = [1.0 if r > 0 else -1.0 for r in _DAILY_RETURNS]

    result = _validator(n_permutations=200).validate(_run(weights))

    assert result.method == "permutation"
    assert result.detail["p_value"] == pytest.approx(1 / 201)
    assert result.detail["percentile"] == 1.0
    assert result.passed is True


def test_constant_long_position_is_indistinguishable_from_chance() -> None:
    # Pure long bias: any shuffle of returns gives the same Sharpe, so p = 1.
    result = _validator().validate(_run([1.0] * len(_DAILY_RETURNS)))

    assert result.detail["p_value"] == pytest.approx(1.0)
    assert result.passed is None


def test_same_seed_reproduces_the_result() -> None:
    weights = [1.0 if i % 3 else -1.0 for i in range(len(_DAILY_RETURNS))]

    first = _validator().validate(_run(weights, seed=7))
    second = _validator().validate(_run(weights, seed=7))
    other = _validator().validate(_run(weights, seed=8))

    assert first.detail == second.detail
    assert other.detail["null_mean"] != first.detail["null_mean"]


def test_short_series_is_flagged_low_confidence() -> None:
    weights = [1.0 if r > 0 else -1.0 for r in _DAILY_RETURNS[:100]] + [0.0] * 300

    result = _validator().validate(_run(weights))

    assert result.detail["active_days"] == 100
    assert result.detail["low_confidence"] is True


def test_no_positions_is_inconclusive_with_a_reason() -> None:
    result = _validator().validate(_run([0.0] * len(_DAILY_RETURNS)))

    assert result.passed is None
    assert "undefined" in result.detail["reason"]


def test_misaligned_price_history_raises() -> None:
    validator = PermutationTestValidator(
        bars={"a": _bars(_DAILY_RETURNS), "b": _bars(_DAILY_RETURNS[:50])},
        n_permutations=10,
        alpha=0.1,
        periods_per_year=365,
    )

    with pytest.raises(ValueError, match="aligned price history"):
        validator.validate(_run([1.0] * len(_DAILY_RETURNS)))
