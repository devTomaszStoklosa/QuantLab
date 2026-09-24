from datetime import date, timedelta

import pytest

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.reporting.cost_comparison import RunMetrics, cost_sensitivity, run_metrics
from quantlab.reporting.metrics import cagr, calmar, max_drawdown, sharpe, sortino


def _metrics(name: str, cagr_value: float, sharpe_value: float) -> RunMetrics:
    return RunMetrics(
        cost_model_name=name,
        cagr=cagr_value,
        sharpe=sharpe_value,
        sortino=0.0,
        calmar=0.0,
        max_drawdown=-0.1,
        turnover=0.0,
    )


def test_run_metrics_computes_each_metric_from_the_equity_curve() -> None:
    equity = [1.0, 1.1, 0.9, 1.05, 1.2]
    start = date(2026, 1, 1)
    run = BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="naive-10bps",
        universe_name="u",
        start=start,
        end=start + timedelta(days=len(equity) - 1),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(ts=start + timedelta(days=i), cash=0.0, positions={}, equity=value)
            for i, value in enumerate(equity)
        ],
    )
    returns = [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]

    result = run_metrics(run, periods_per_year=365)

    assert result.cost_model_name == "naive-10bps"
    assert result.cagr == pytest.approx(cagr(equity, 365))
    assert result.sharpe == pytest.approx(sharpe(returns, 365))
    assert result.sortino == pytest.approx(sortino(returns, 365))
    assert result.calmar == pytest.approx(calmar(equity, 365))
    assert result.max_drawdown == pytest.approx(max_drawdown(equity))


def test_small_sharpe_gap_without_sign_flip_is_robust() -> None:
    result = cost_sensitivity(_metrics("naive", 0.10, 0.50), _metrics("realistic", 0.09, 0.45))

    assert result.sharpe_difference == pytest.approx(0.05)
    assert not result.cagr_sign_flip
    assert result.verdict == "robust"


def test_large_sharpe_gap_is_cost_dependent_even_without_sign_flip() -> None:
    result = cost_sensitivity(_metrics("naive", 0.10, 0.50), _metrics("realistic", 0.05, 0.30))

    assert not result.cagr_sign_flip
    assert result.verdict == "cost-dependent"


def test_cagr_sign_flip_is_cost_dependent_even_with_small_sharpe_gap() -> None:
    result = cost_sensitivity(_metrics("naive", 0.02, 0.12), _metrics("realistic", -0.01, 0.05))

    assert result.cagr_sign_flip
    assert result.verdict == "cost-dependent"


def _traded_run(traded: list[dict[str, float]]) -> BacktestRun:
    start = date(2026, 1, 1)
    equity = [1.0, 1.01, 0.99, 1.02, 1.0, 1.03][: len(traded)]
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=start,
        end=start + timedelta(days=len(traded) - 1),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(
                ts=start + timedelta(days=i), cash=0.0, positions={}, equity=value, traded=day
            )
            for i, (value, day) in enumerate(zip(equity, traded, strict=True))
        ],
    )


def test_turnover_counts_from_the_first_trade() -> None:
    run = _traded_run([{}, {}, {"a": 1.0}, {}, {"a": 0.5, "b": 0.5}, {}])

    # Periods 2..5 after the warm-up: 2.0 traded over 4 periods.
    assert run_metrics(run, periods_per_year=365).turnover == pytest.approx(2.0 / 4 * 365)


def test_turnover_is_zero_without_trades() -> None:
    run = _traded_run([{}, {}, {}, {}, {}, {}])
    run = run.model_copy(
        update={
            "snapshots": [
                snapshot.model_copy(update={"equity": value})
                for snapshot, value in zip(
                    run.snapshots, [1.0, 1.1, 0.9, 1.05, 1.2, 1.1], strict=True
                )
            ]
        }
    )

    assert run_metrics(run, periods_per_year=365).turnover == 0.0


def test_a_run_that_never_traded_has_undefined_ratios_not_an_error() -> None:
    flat = _traded_run([{}, {}, {}, {}, {}, {}])
    flat = flat.model_copy(
        update={"snapshots": [s.model_copy(update={"equity": 1.0}) for s in flat.snapshots]}
    )

    metrics = run_metrics(flat, periods_per_year=365)

    assert (metrics.sharpe, metrics.sortino, metrics.calmar) == (None, None, None)
    assert (metrics.cagr, metrics.max_drawdown, metrics.turnover) == (0.0, 0.0, 0.0)


def test_cost_sensitivity_is_undefined_without_a_sharpe_to_compare() -> None:
    defined = _metrics("naive", 0.05, 0.4)
    undefined = defined.model_copy(update={"cost_model_name": "realistic", "sharpe": None})

    sensitivity = cost_sensitivity(lower_cost=defined, higher_cost=undefined)

    assert sensitivity.verdict == "undefined"
    assert (sensitivity.sharpe_difference, sensitivity.cagr_sign_flip) == (None, None)
