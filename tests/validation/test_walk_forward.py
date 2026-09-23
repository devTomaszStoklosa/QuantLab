from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.vectorized.engine import BacktestRun, PortfolioSnapshot
from quantlab.reporting.metrics import cagr, max_drawdown, sharpe
from quantlab.validation.base import Validator
from quantlab.validation.walk_forward import WalkForwardValidator

_START = date(2026, 1, 1)


def _run(returns: list[float]) -> BacktestRun:
    equity = [1.0]
    for period_return in returns:
        equity.append(equity[-1] * (1.0 + period_return))
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_START,
        end=_START + timedelta(days=len(returns)),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(ts=_START + timedelta(days=i), cash=0.0, positions={}, equity=value)
            for i, value in enumerate(equity)
        ],
    )


def _noisy(n: int, mean: float, seed: int = 1) -> list[float]:
    return (mean + 0.01 * np.random.default_rng(seed).standard_normal(n)).tolist()


def test_folds_roll_forward_with_train_immediately_before_test() -> None:
    run = _run(_noisy(23, 0.001))
    validator = WalkForwardValidator(train_periods=6, test_periods=5, periods_per_year=365)

    report = validator.report(run)

    # Returns are dated by the snapshot they end on: day 1 .. day 23.
    day = lambda k: _START + timedelta(days=k)
    assert [(f.train.start, f.train.end, f.test.start, f.test.end) for f in report.folds] == [
        (day(1), day(6), day(7), day(11)),
        (day(6), day(11), day(12), day(16)),
        (day(11), day(16), day(17), day(21)),
    ]
    assert [f.index for f in report.folds] == [0, 1, 2]
    assert all(f.train.end < f.test.start for f in report.folds)
    assert report.unused_trailing_periods == 2


def test_window_metrics_match_metrics_computed_on_the_slice() -> None:
    returns = _noisy(20, 0.002)
    validator = WalkForwardValidator(train_periods=8, test_periods=6, periods_per_year=365)

    fold = validator.report(_run(returns)).folds[0]

    test_returns = returns[8:14]
    test_equity = np.concatenate(([1.0], np.cumprod(1.0 + np.asarray(test_returns)))).tolist()
    assert fold.test.periods == 6
    assert fold.test.sharpe == pytest.approx(sharpe(test_returns, 365))
    assert fold.test.cagr == pytest.approx(cagr(test_equity, 365))
    assert fold.test.max_drawdown == pytest.approx(max_drawdown(test_equity))
    assert fold.test.total_return == pytest.approx(test_equity[-1] - 1.0)
    assert fold.train.sharpe == pytest.approx(sharpe(returns[:8], 365))


def test_aggregate_stitches_test_windows_only() -> None:
    returns = _noisy(25, 0.001)
    validator = WalkForwardValidator(train_periods=5, test_periods=5, periods_per_year=365)

    report = validator.report(_run(returns))

    stitched = returns[5:25]
    assert report.aggregate_test.periods == 20
    assert report.aggregate_test.sharpe == pytest.approx(sharpe(stitched, 365))


def test_overlapping_test_windows_count_each_return_once_in_the_aggregate() -> None:
    returns = _noisy(14, 0.001)
    validator = WalkForwardValidator(
        train_periods=4, test_periods=6, step_periods=2, periods_per_year=365
    )

    report = validator.report(_run(returns))

    assert len(report.folds) == 3
    assert report.aggregate_test.periods == 10
    assert report.aggregate_test.sharpe == pytest.approx(sharpe(returns[4:14], 365))


def test_consistent_positive_result_passes() -> None:
    validator = WalkForwardValidator(train_periods=20, test_periods=20, periods_per_year=365)

    result = validator.validate(_run(_noisy(120, 0.005)))

    assert result.method == "walk_forward"
    assert result.passed is True
    assert len(result.detail["folds"]) == 5
    assert result.detail["positive_test_fraction"] == 1.0


def test_negative_out_of_sample_result_fails() -> None:
    validator = WalkForwardValidator(train_periods=20, test_periods=20, periods_per_year=365)

    result = validator.validate(_run(_noisy(120, -0.005)))

    assert result.passed is False
    assert result.detail["reason"] == "criterion not met"


def test_positive_aggregate_driven_by_one_window_fails_the_consistency_rule() -> None:
    # Four quiet losing windows and one big winner: the stitched Sharpe is positive,
    # but only 1 of 5 test windows is.
    losing = [-0.002, 0.001] * 10
    winning = [0.03, 0.01] * 10
    returns = _noisy(20, 0.0) + losing * 4 + winning
    validator = WalkForwardValidator(train_periods=20, test_periods=20, periods_per_year=365)

    result = validator.validate(_run(returns))

    assert result.detail["aggregate_test"]["sharpe"] > 0
    assert result.detail["positive_test_fraction"] == pytest.approx(0.2)
    assert result.passed is False


def test_too_few_folds_is_inconclusive_not_a_pass_or_fail() -> None:
    validator = WalkForwardValidator(train_periods=20, test_periods=20, periods_per_year=365)

    result = validator.validate(_run(_noisy(60, 0.005)))

    assert len(result.detail["folds"]) == 2
    assert result.passed is None
    assert result.detail["reason"] == "only 2 full folds, need 3"


def test_run_shorter_than_one_fold_reports_no_folds() -> None:
    validator = WalkForwardValidator(train_periods=20, test_periods=20, periods_per_year=365)

    result = validator.validate(_run(_noisy(30, 0.005)))

    assert result.passed is None
    assert result.detail["folds"] == []
    assert result.detail["aggregate_test"] is None
    assert result.detail["unused_trailing_periods"] == 30


def test_flat_window_has_no_sharpe_and_does_not_count_as_positive() -> None:
    returns = [0.0] * 10 + _noisy(10, 0.005) + [0.0] * 10 + _noisy(10, 0.005, seed=2)
    validator = WalkForwardValidator(
        train_periods=10, test_periods=10, periods_per_year=365, min_folds=1
    )

    report = validator.report(_run(returns))

    assert report.folds[1].test.sharpe is None
    assert report.folds[1].test.total_return == 0.0
    assert report.positive_test_fraction == pytest.approx(2 / 3)


def test_criterion_is_recorded_in_the_result() -> None:
    validator = WalkForwardValidator(
        train_periods=20, test_periods=20, periods_per_year=365,
        min_test_sharpe=0.5, min_positive_fraction=0.6, min_folds=4,
    )

    result = validator.validate(_run(_noisy(120, 0.005)))

    assert result.detail["criterion"] == {
        "min_test_sharpe": 0.5,
        "min_positive_fraction": 0.6,
        "min_folds": 4,
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"train_periods": 0, "test_periods": 5},
        {"train_periods": 5, "test_periods": 1},
        {"train_periods": 5, "test_periods": 5, "step_periods": 0},
        {"train_periods": 5, "test_periods": 5, "min_positive_fraction": 1.5},
    ],
)
def test_invalid_configuration_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        WalkForwardValidator(periods_per_year=365, **kwargs)


def test_satisfies_validator_protocol() -> None:
    validator: Validator = WalkForwardValidator(
        train_periods=5, test_periods=5, periods_per_year=365
    )

    assert validator.validate(_run(_noisy(30, 0.001))).method == "walk_forward"
