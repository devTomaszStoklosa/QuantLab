from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.reporting.multiple_testing import active_returns, multiple_testing
from quantlab.research.trials import Trial
from quantlab.validation.holdout import parse_holdout_config
from quantlab.validation.sharpe_inference import (
    deflated_sharpe_ratio,
    probabilistic_sharpe_ratio,
    sharpe_statistics,
)

_FIRST_DAY = date(2020, 1, 1)


def _run(returns: list[float], warm_up_days: int = 0) -> BacktestRun:
    """`warm_up_days` flat days without positions, then one return per held day."""
    all_returns = [0.0] * warm_up_days + returns
    equity = np.cumprod([1.0, *(1.0 + r for r in all_returns)])
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_FIRST_DAY,
        end=_FIRST_DAY + timedelta(days=len(all_returns)),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(
                ts=_FIRST_DAY + timedelta(days=i),
                cash=0.0,
                positions={"a": 1.0} if i > warm_up_days else {},
                equity=float(value),
            )
            for i, value in enumerate(equity)
        ],
    )


_DEFINITION = parse_holdout_config(
    Path(__file__).parents[2] / "config" / "holdout" / "momentum_v1.yaml"
)


def _trial(hypothesis: str) -> Trial:
    return Trial(
        hypothesis=hypothesis,
        universe="mvp-crypto",
        training_start=date(2018, 1, 1),
        training_end=date(2023, 12, 31),
        registered_at=datetime(2026, 9, 23, tzinfo=UTC),
        last_commit="abc",
        deleted=False,
        path=f"{hypothesis}.yaml",
        definition=_DEFINITION.model_copy(update={"hypothesis": hypothesis}),
    )


_RETURNS = list(np.random.default_rng(4).normal(0.002, 0.03, 400))


def test_active_returns_start_at_the_first_held_position() -> None:
    returns = active_returns(_run(_RETURNS, warm_up_days=30))

    assert returns == pytest.approx(_RETURNS)


def test_one_trial_leaves_nothing_to_deflate() -> None:
    result = multiple_testing(_run(_RETURNS, warm_up_days=5), [_trial("only_v1")], 365)

    statistics = sharpe_statistics(_RETURNS)
    assert result.trials == ["only_v1"]
    assert result.n_returns == 400
    assert result.psr == pytest.approx(probabilistic_sharpe_ratio(statistics))
    assert result.threshold_annualized == 0.0
    assert result.dsr == pytest.approx(result.psr)
    assert result.sharpe_annualized == pytest.approx(statistics.sharpe * 365**0.5)


def test_each_further_trial_on_the_same_data_raises_the_bar() -> None:
    trials = [_trial("first_v1"), _trial("second_v1")]

    result = multiple_testing(_run(_RETURNS), trials, 365)

    assert result.threshold_annualized > 0
    assert result.dsr == pytest.approx(deflated_sharpe_ratio(sharpe_statistics(_RETURNS), 2))
    assert result.dsr < result.psr


def test_a_run_without_positions_has_no_psr_or_dsr() -> None:
    run = _run([], warm_up_days=10)

    result = multiple_testing(run, [_trial("idle_v1")], 365)

    assert (result.n_returns, result.psr, result.dsr, result.threshold_annualized) == (
        0,
        None,
        None,
        None,
    )


def test_a_run_is_always_one_of_its_trials() -> None:
    with pytest.raises(ValueError, match="own trials"):
        multiple_testing(_run(_RETURNS), [], 365)
