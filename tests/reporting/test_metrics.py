import math
import statistics

import pytest

from quantlab.reporting.metrics import (
    cagr,
    calmar,
    drawdown_series,
    max_drawdown,
    sharpe,
    sortino,
)


def test_cagr_over_two_years() -> None:
    # total growth 1.21 over 4 periods at 2 periods/year = 2 years -> sqrt(1.21) - 1
    equity_curve = [1.0, 1.05, 1.10, 1.15, 1.21]

    assert cagr(equity_curve, periods_per_year=2) == pytest.approx(0.10)


def test_cagr_raises_with_fewer_than_two_points() -> None:
    with pytest.raises(ValueError, match="at least 2 equity points"):
        cagr([1.0], periods_per_year=365)


def test_cagr_raises_when_total_growth_not_positive() -> None:
    with pytest.raises(ValueError, match="zero or negative"):
        cagr([1.0, 0.0], periods_per_year=365)


def test_sharpe_matches_manual_calculation() -> None:
    returns = [0.04, -0.02, 0.04, -0.02]
    periods_per_year = 365
    expected = (
        statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(periods_per_year)
    )

    assert sharpe(returns, periods_per_year) == pytest.approx(expected)


def test_sharpe_raises_on_zero_variance() -> None:
    with pytest.raises(ValueError, match="zero variance"):
        sharpe([0.01, 0.01, 0.01], periods_per_year=365)


def test_sharpe_raises_with_fewer_than_two_returns() -> None:
    with pytest.raises(ValueError, match="at least 2 return periods"):
        sharpe([0.01], periods_per_year=365)


def test_sortino_matches_manual_downside_deviation_calculation() -> None:
    returns = [0.05, -0.03, 0.02, -0.01]
    periods_per_year = 365
    downside_squared = [min(r, 0.0) ** 2 for r in returns]
    downside_deviation = (sum(downside_squared) / len(returns)) ** 0.5
    expected = (sum(returns) / len(returns)) / downside_deviation * (periods_per_year**0.5)

    assert sortino(returns, periods_per_year) == pytest.approx(expected)


def test_sortino_raises_when_no_returns_below_target() -> None:
    with pytest.raises(ValueError, match="no returns below target"):
        sortino([0.01, 0.02, 0.03], periods_per_year=365)


def test_max_drawdown_finds_largest_peak_to_trough_decline() -> None:
    equity_curve = [1.0, 1.2, 0.9, 1.1]

    assert max_drawdown(equity_curve) == pytest.approx(-0.25)


def test_max_drawdown_is_zero_for_monotonically_increasing_curve() -> None:
    assert max_drawdown([1.0, 1.1, 1.2]) == 0.0


def test_drawdown_series_measures_each_point_against_its_running_peak() -> None:
    equity_curve = [1.0, 1.2, 0.9, 1.1, 1.3]

    assert drawdown_series(equity_curve) == pytest.approx([0.0, 0.0, -0.25, -1 / 12, 0.0])


def test_drawdown_series_raises_on_empty_curve() -> None:
    with pytest.raises(ValueError):
        drawdown_series([])


def test_calmar_composes_cagr_and_max_drawdown() -> None:
    equity_curve = [1.0, 1.2, 0.9, 1.1]
    periods_per_year = 365
    expected = cagr(equity_curve, periods_per_year) / abs(max_drawdown(equity_curve))

    assert calmar(equity_curve, periods_per_year) == pytest.approx(expected)


def test_calmar_raises_when_no_drawdown() -> None:
    with pytest.raises(ValueError, match="no drawdown"):
        calmar([1.0, 1.1, 1.2], periods_per_year=365)
