from datetime import date, timedelta

import pytest

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.reporting.metrics import cagr
from quantlab.validation.walk_forward import WalkForwardValidator

_PERIODS_PER_YEAR = 365


def _run(first_day: date, daily_returns: list[float], first_position: int = 1) -> BacktestRun:
    equity = [1.0]
    for daily_return in daily_returns:
        equity.append(equity[-1] * (1.0 + daily_return))
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=first_day,
        end=first_day + timedelta(days=len(daily_returns)),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(
                ts=first_day + timedelta(days=i),
                cash=0.0,
                positions={"a": 1.0} if i >= first_position else {},
                equity=value,
            )
            for i, value in enumerate(equity)
        ],
    )


def _year_returns(year: int, drift: float) -> list[float]:
    # Alternating noise keeps variance non-zero; the drift sets the Sharpe's sign.
    days = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    return [drift + (0.005 if i % 2 == 0 else -0.005) for i in range(days)]


def _run_over_years(drifts: dict[int, float]) -> BacktestRun:
    first_year = min(drifts)
    returns = [r for year in sorted(drifts) for r in _year_returns(year, drifts[year])]
    # Snapshot 0 on Dec 31 of the prior year is flat; positions start Jan 1.
    return _run(date(first_year - 1, 12, 31), returns)


def test_windows_are_calendar_years_from_first_position_in_order() -> None:
    # Flat warm-up on Dec 30; first position Dec 31; run ends Jan 2.
    run = _run(date(2020, 12, 30), [0.01, 0.02, -0.01], first_position=1)

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    windows = result.detail["windows"]
    assert [(w["start"], w["end"], w["partial"]) for w in windows] == [
        ("2020-12-31", "2020-12-31", True),
        ("2021-01-01", "2021-01-02", True),
    ]


def test_window_first_return_is_measured_from_previous_day_equity() -> None:
    run = _run(date(2020, 12, 30), [0.01, 0.02, -0.01], first_position=1)
    equity = [snapshot.equity for snapshot in run.snapshots]

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    # Snapshots: Dec 30, Dec 31, Jan 1, Jan 2. The 2021 window's base is
    # Dec 31's equity, then Jan 1 and Jan 2.
    expected = cagr([equity[1], equity[2], equity[3]], _PERIODS_PER_YEAR)
    assert result.detail["windows"][1]["cagr"] == pytest.approx(expected)


def test_undefined_window_metric_is_none_not_an_error() -> None:
    # The 2020 window (Dec 31 only) has a single return, so no Sharpe.
    run = _run(date(2020, 12, 30), [0.01, 0.02, -0.01], first_position=1)

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.detail["windows"][0]["sharpe"] is None


def test_passes_with_two_of_three_positive_windows_and_positive_aggregate() -> None:
    run = _run_over_years({2019: 0.001, 2020: 0.001, 2021: -0.001})

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.method == "walk_forward"
    assert result.detail["positive_windows"] == 2
    assert result.detail["windows_with_sharpe"] == 3
    assert result.passed is True


def test_fails_with_fewer_than_two_thirds_positive_windows() -> None:
    run = _run_over_years({2019: 0.001, 2020: -0.001, 2021: -0.001})

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.passed is False


def test_fails_when_aggregate_sharpe_is_not_positive() -> None:
    run = _run_over_years({2019: 0.0005, 2020: 0.0005, 2021: -0.003})

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.detail["positive_windows"] == 2
    assert result.detail["aggregate"]["sharpe"] < 0
    assert result.passed is False


def test_inconclusive_with_fewer_than_three_windows() -> None:
    run = _run_over_years({2019: 0.001, 2020: 0.001})

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.passed is None


def test_inconclusive_when_no_position_is_ever_held() -> None:
    run = _run(date(2020, 1, 1), [0.0, 0.0, 0.0], first_position=10)

    result = WalkForwardValidator(_PERIODS_PER_YEAR).validate(run)

    assert result.passed is None
    assert result.detail["windows"] == []
