import json
import math
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest

from quantlab.attribution.trade_ledger import (
    HOLDING_PERIOD_BUCKETS,
    build_trade_ledger,
    by_holding_period,
    by_regime,
    group_pnl,
)
from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.core.data.provider import PriceBar
from quantlab.reporting.cost_comparison import cost_sensitivity, run_metrics
from quantlab.reporting.grid_report import GridReport, grid_report
from quantlab.reporting.metrics import drawdown_series
from quantlab.reporting.multiple_testing import MultipleTesting
from quantlab.reporting.results_store import (
    NARRATIVE_FILE,
    NARRATIVE_SCHEMA,
    REGISTRY_FILE,
    REGISTRY_SCHEMA,
    RUN_FILE,
    RUN_SCHEMA,
    SCHEMA_VERSION,
    TABLE_SCHEMAS,
    RunEvidence,
    registry_rows,
    write_registry,
    write_run,
)
from quantlab.reporting.tear_sheet import TearSheet
from quantlab.research.definition import GridEvidence, TrainingDiagnostic
from quantlab.risk.conditional import regime_conditional_metrics
from quantlab.risk.regime import VOLATILITY_REGIMES
from quantlab.strategy.selected_parameter import SelectionRecord
from quantlab.validation.base import ValidationResult
from quantlab.validation.cpcv import CPCV_GATE_RULE, CpcvSettings
from quantlab.validation.holdout import HoldoutRecord, write_holdout_record
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.walk_forward import WalkForwardValidator

_FIRST_DAY = date(2020, 1, 1)
_DAYS = 800
_PERIODS_PER_YEAR = 365
_PATTERN = [0.02, -0.01, 0.03, -0.02, 0.01, -0.03, 0.015, -0.005, 0.025, -0.017]
_REAL_DEFINITIONS = Path(__file__).parents[2] / "config" / "holdout"


def _day(i: int) -> date:
    return _FIRST_DAY + timedelta(days=i)


def _closes() -> list[float]:
    closes = [100.0]
    for i in range(_DAYS):
        closes.append(closes[-1] * (1.0 + _PATTERN[i % len(_PATTERN)]))
    return closes


def _bars() -> dict[str, list[PriceBar]]:
    return {
        "a": [
            PriceBar(
                instrument_id="a",
                ts=_day(i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
                adj_close=None,
                source="synthetic",
            )
            for i, close in enumerate(_closes())
        ]
    }


def _run(held: bool = True, run_id: str = "run-1") -> BacktestRun:
    """Long instrument "a" from day 1 in 100-day stretches, so there are several trades."""
    closes = _closes()
    equity, snapshots = 1.0, []
    for i, close in enumerate(closes):
        position = held and i > 0 and (i // 100) % 2 == 0
        if i > 0 and snapshots[-1].positions:
            equity *= close / closes[i - 1]
        snapshots.append(
            PortfolioSnapshot(
                ts=_day(i), cash=0.0, positions={"a": 1.0} if position else {}, equity=equity
            )
        )
    return BacktestRun(
        id=run_id,
        strategy_name="time_series_momentum",
        strategy_params={"lookback_days": 365},
        cost_model_name="realistic",
        universe_name="test-universe",
        start=_FIRST_DAY,
        end=_day(_DAYS),
        seed=0,
        git_sha="0123456789abcdef",
        snapshots=snapshots,
    )


def _evidence(
    run: BacktestRun | None = None,
    hypothesis: str = "momentum_v1",
    walk_forward: ValidationResult | None = None,
    diagnostics: list[TrainingDiagnostic] | None = None,
    grid: GridReport | None = None,
    in_sample_validation: str = "walk_forward",
) -> RunEvidence:
    run = run or _run()
    labels = {_day(i): ("low" if i % 3 else "high") for i in range(_DAYS + 1)}
    metrics = run_metrics(run, _PERIODS_PER_YEAR)
    naive = metrics.model_copy(update={"cost_model_name": "naive-10bps"})
    trades = build_trade_ledger(run, _bars(), labels)
    sheet = TearSheet(
        hypothesis=hypothesis,
        run=run,
        cost_comparison=[
            metrics.model_copy(update={"cost_model_name": "zero-cost"}),
            naive,
            metrics,
        ],
        regimes=regime_conditional_metrics(run, labels, _PERIODS_PER_YEAR),
        regime_method="Test regimes.",
        walk_forward=walk_forward or WalkForwardValidator(_PERIODS_PER_YEAR).validate(run),
        permutation=PermutationTestValidator(
            bars=_bars(), n_permutations=50, alpha=0.1, periods_per_year=_PERIODS_PER_YEAR
        ).validate(run),
        holdout=None,
        generated_at=datetime(2026, 9, 24, 10, 0, tzinfo=UTC),
        grid=grid,
        in_sample_validation=in_sample_validation,
        multiple_testing=MultipleTesting(
            trials=["momentum_v1", "mean_reversion_v1"],
            configurations=2,
            n_returns=700,
            sharpe_annualized=metrics.sharpe,
            psr=0.9,
            threshold_annualized=0.4,
            dsr=0.8,
        ),
    )
    groups = group_pnl(trades, by_holding_period)
    return RunEvidence(
        sheet=sheet,
        cost_sensitivity=cost_sensitivity(lower_cost=naive, higher_cost=metrics),
        trades=trades,
        pnl_groups={
            "regime": group_pnl(trades, by_regime),
            "holding_period": {key: groups[key] for key in HOLDING_PERIOD_BUCKETS if key in groups},
        },
        diagnostics=diagnostics or [],
        data_source="synthetic",
    )


def _read(path: Path) -> list[dict]:
    return pq.read_table(path).to_pylist()


def test_the_run_tables_hold_the_numbers_the_run_computed(tmp_path) -> None:
    evidence = _evidence()
    run = evidence.sheet.run

    directory = write_run(tmp_path, evidence)

    assert directory == tmp_path / "momentum_v1"
    [row] = _read(directory / RUN_FILE)
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["run_id"] == "run-1"
    assert json.loads(row["strategy_params"]) == {"lookback_days": 365}
    assert row["first_position"] == _day(1)
    assert row["data_source"] == "synthetic"
    assert row["walk_forward_passed"] == evidence.sheet.walk_forward.passed
    assert row["permutation_p_value"] == evidence.sheet.permutation.detail["p_value"]
    assert row["permutation_test"] == "day_shuffle"
    assert row["trials"] == ["momentum_v1", "mean_reversion_v1"]
    assert row["dsr"] == 0.8
    assert row["trades"] == len(evidence.trades) > 2
    assert row["contrast_hypothesis"] is None

    metrics = _read(directory / "metrics.parquet")
    assert [m["cost_model"] for m in metrics] == ["zero-cost", "naive-10bps", "realistic"]
    assert [m["primary"] for m in metrics] == [False, False, True]
    assert metrics[2]["sharpe"] == evidence.sheet.cost_comparison[2].sharpe

    equity = _read(directory / "equity.parquet")
    assert [point["equity"] for point in equity] == [s.equity for s in run.snapshots]
    assert [point["drawdown"] for point in equity] == drawdown_series(
        [s.equity for s in run.snapshots]
    )

    windows = _read(directory / "walk_forward.parquet")
    assert [window["aggregate"] for window in windows] == [False, False, False, True]
    assert windows[0]["start"] == _day(1)

    regimes = _read(directory / "regimes.parquet")
    assert [regime["regime"] for regime in regimes] == ["low", "high"]
    assert math.fsum(regime["share"] for regime in regimes) == pytest.approx(1.0)

    monthly = _read(directory / "monthly.parquet")
    assert (monthly[0]["year"], monthly[0]["month"]) == (2020, 1)
    assert math.prod(1.0 + m["net_return"] for m in monthly) == pytest.approx(
        run.snapshots[-1].equity / run.snapshots[0].equity
    )

    yearly = _read(directory / "yearly.parquet")
    assert [y["year"] for y in yearly] == [2020, 2021, 2022]
    assert math.prod(1.0 + y["net_return"] for y in yearly) == pytest.approx(
        run.snapshots[-1].equity / run.snapshots[0].equity
    )

    trades = _read(directory / "trades.parquet")
    assert [trade["trade_id"] for trade in trades] == list(range(1, len(evidence.trades) + 1))
    assert trades[0]["net_pnl"] == evidence.trades[0].net_pnl

    groups = _read(directory / "pnl_groups.parquet")
    assert {group["dimension"] for group in groups} == {"regime", "holding_period"}


def test_every_table_has_the_declared_schema(tmp_path) -> None:
    directory = write_run(tmp_path, _evidence())

    assert pq.read_schema(directory / RUN_FILE).remove_metadata() == RUN_SCHEMA
    for name, schema in TABLE_SCHEMAS.items():
        assert pq.read_schema(directory / f"{name}.parquet").remove_metadata() == schema


def test_undefined_numbers_are_stored_as_null(tmp_path) -> None:
    diagnostic = TrainingDiagnostic(
        title="Cointegration", values={"p-value": 0.5, "half-life": None, "broken": math.nan}
    )
    directory = write_run(tmp_path, _evidence(_run(held=False), diagnostics=[diagnostic]))

    [row] = _read(directory / RUN_FILE)
    assert row["first_position"] is None
    assert row["permutation_p_value"] is None
    assert row["permutation_reason"] is not None
    assert row["trades"] == 0
    [metrics] = [m for m in _read(directory / "metrics.parquet") if m["primary"]]
    assert metrics["sharpe"] is None
    assert _read(directory / "trades.parquet") == []
    assert [d["value"] for d in _read(directory / "diagnostics.parquet")] == [0.5, None, None]


def test_a_new_run_replaces_the_previous_one_as_a_whole(tmp_path) -> None:
    first = write_run(tmp_path, _evidence(_run(run_id="first")))
    (first / "left-over.parquet").write_bytes(b"")

    second = write_run(tmp_path, _evidence(_run(run_id="second")))

    assert second == first
    assert [row["run_id"] for row in _read(second / RUN_FILE)] == ["second"]
    assert not (second / "left-over.parquet").exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["momentum_v1"]


def test_the_store_needs_the_multiple_testing_result() -> None:
    evidence = _evidence()
    sheet = evidence.sheet.model_copy(update={"multiple_testing": None})

    with pytest.raises(ValueError, match="multiple-testing"):
        RunEvidence.model_validate(evidence.model_dump() | {"sheet": sheet})


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _definitions(repo: Path) -> Path:
    """Three definitions on the same data, committed one by one; the third later deleted."""
    repo.mkdir()
    _git(repo, "init", "-q")
    text = (_REAL_DEFINITIONS / "momentum_v1.yaml").read_text(encoding="utf-8")
    for hypothesis in ("momentum_v1", "reversal_v1", "dropped_v1"):
        (repo / f"{hypothesis}.yaml").write_text(
            text.replace("hypothesis: momentum_v1", f"hypothesis: {hypothesis}"), encoding="utf-8"
        )
        _git(repo, "add", f"{hypothesis}.yaml")
        _git(repo, "commit", "-q", "-m", f"freeze {hypothesis}")
    _git(repo, "rm", "-q", "dropped_v1.yaml")
    _git(repo, "commit", "-q", "-m", "drop dropped_v1")
    return repo


def _opened(verdict: str) -> HoldoutRecord:
    return HoldoutRecord(
        hypothesis="momentum_v1",
        frozen_at_commit="a" * 40,
        opened_at=datetime(2026, 9, 23, 14, 1, tzinfo=UTC),
        opened_at_commit="b" * 40,
        start=date(2024, 1, 1),
        end=date(2025, 12, 31),
        cost_model_name="realistic-10bps-k0.05-vol30d",
        cagr=0.06,
        sharpe=0.37,
        sortino=0.54,
        calmar=0.13,
        max_drawdown=-0.48,
        p_value=0.61,
        permutation={},
        criterion="Holdout net Sharpe > 0 and p < 0.1",
        verdict=verdict,
    )


def test_the_registry_lists_each_committed_definition_with_its_git_facts(tmp_path) -> None:
    repo = _definitions(tmp_path / "definitions")

    rows = write_registry(tmp_path / "results", repo)

    assert [row.hypothesis for row in rows] == ["momentum_v1", "reversal_v1"]
    momentum = rows[0]
    assert (
        momentum.frozen_at_commit
        == _git(repo, "log", "-1", "--format=%H", "--", "momentum_v1.yaml").strip()
    )
    assert momentum.trials_on_same_data == 3  # the deleted definition still counts
    assert momentum.cost_model == "realistic-10bps-k0.05-vol30d"
    assert json.loads(momentum.parameters)["lookback_days"] == 365
    assert (momentum.training_start, momentum.holdout_end) == (date(2018, 1, 1), date(2025, 12, 31))
    assert [row.status for row in rows] == ["proposed", "proposed"]
    stored = _read(tmp_path / "results" / REGISTRY_FILE)
    assert pq.read_schema(tmp_path / "results" / REGISTRY_FILE).remove_metadata() == REGISTRY_SCHEMA
    assert [row["hypothesis"] for row in stored] == ["momentum_v1", "reversal_v1"]
    assert stored[0]["holdout_verdict"] is None
    assert stored[0]["schema_version"] == SCHEMA_VERSION
    # Frozen before q5, the definitions name no significance test: the day shuffle.
    assert [row["significance_test"] for row in stored] == ["day_shuffle", "day_shuffle"]


def _walk_forward(passed: bool | None) -> ValidationResult:
    return ValidationResult(
        method="walk_forward",
        passed=passed,
        detail={"rule": "test", "windows": [], "aggregate": None},
    )


@pytest.mark.parametrize(
    ("walk_forward_passed", "verdict", "status"),
    [
        (True, "passed", "confirmed"),
        (True, "inconclusive", "inconclusive"),
        (True, "rejected", "rejected"),
        (False, "passed", "rejected"),
        (None, "passed", "inconclusive"),
    ],
)
def test_an_opened_holdout_concludes_the_status_with_the_stored_walk_forward(
    tmp_path, walk_forward_passed, verdict, status
) -> None:
    repo = _definitions(tmp_path / "definitions")
    store = tmp_path / "results"
    write_run(store, _evidence(walk_forward=_walk_forward(walk_forward_passed)))
    write_holdout_record(repo / "momentum_v1.opened.json", _opened(verdict))

    rows = write_registry(store, repo)

    assert rows[0].status == status
    stored = _read(store / REGISTRY_FILE)[0]
    assert stored["holdout_verdict"] == verdict
    assert stored["holdout_sharpe"] == 0.37
    assert stored["has_run"] is True


def test_the_registry_refresh_writes_a_narrative_that_follows_the_opening(tmp_path) -> None:
    repo = _definitions(tmp_path / "definitions")
    store = tmp_path / "results"
    write_run(store, _evidence(walk_forward=_walk_forward(True)))

    write_registry(store, repo)
    sealed = _read(store / "momentum_v1" / NARRATIVE_FILE)
    write_holdout_record(repo / "momentum_v1.opened.json", _opened("inconclusive"))
    write_registry(store, repo)
    opened = _read(store / "momentum_v1" / NARRATIVE_FILE)

    schema = pq.read_schema(store / "momentum_v1" / NARRATIVE_FILE).remove_metadata()
    assert schema == NARRATIVE_SCHEMA
    assert [row["position"] for row in opened] == list(range(len(opened)))
    assert any(row["text"].startswith("Holdout nieotwarty.") for row in sealed)
    assert "Werdykt holdoutu: inconclusive (kryterium: Holdout net Sharpe > 0 and p < 0.1)" in {
        row["text"] for row in opened
    }
    # Only hypotheses with a stored run get one.
    assert not (store / "reversal_v1" / NARRATIVE_FILE).exists()


def test_a_stored_run_before_the_opening_means_testing(tmp_path) -> None:
    repo = _definitions(tmp_path / "definitions")
    store = tmp_path / "results"
    write_run(store, _evidence(hypothesis="reversal_v1"))

    rows = registry_rows(store, repo)

    assert [(row.hypothesis, row.status, row.has_run) for row in rows] == [
        ("momentum_v1", "proposed", False),
        ("reversal_v1", "testing", True),
    ]


def test_an_opened_holdout_without_a_stored_run_has_no_walk_forward_evidence(tmp_path) -> None:
    repo = _definitions(tmp_path / "definitions")
    write_holdout_record(repo / "momentum_v1.opened.json", _opened("passed"))

    rows = registry_rows(tmp_path / "results", repo)

    assert rows[0].status == "inconclusive"  # confirmed needs both gates


def test_a_run_of_another_schema_version_is_not_counted(tmp_path, monkeypatch) -> None:
    repo = _definitions(tmp_path / "definitions")
    store = tmp_path / "results"
    write_run(store, _evidence(hypothesis="reversal_v1"))
    monkeypatch.setattr("quantlab.reporting.results_store.SCHEMA_VERSION", SCHEMA_VERSION + 1)

    rows = registry_rows(store, repo)

    assert rows[1].has_run is False
    assert rows[1].status == "proposed"


def test_regime_rows_follow_the_regime_order(tmp_path) -> None:
    directory = write_run(tmp_path, _evidence())

    labels = [row["regime"] for row in _read(directory / "regimes.parquet")]

    assert labels == [label for label in VOLATILITY_REGIMES if label in labels]


def _grid(drift: float = 0.0) -> GridReport:
    """Two grid values over 2020-2021, "90" with a lasting edge over "30"; no choice in 2020."""
    returns = np.random.default_rng(5).normal(drift, 0.01, (731, 2))
    returns[:, 1] += 0.002
    history = [
        SelectionRecord(
            year=2020,
            evaluated_from=None,
            evaluated_to=date(2019, 12, 31),
            days=0,
            sharpes={"30": None, "90": None},
            chosen=None,
        ),
        SelectionRecord(
            year=2021,
            evaluated_from=date(2020, 1, 1),
            evaluated_to=date(2020, 12, 31),
            days=366,
            sharpes={"30": -0.01, "90": 0.2},
            chosen="90",
        ),
    ]
    evidence = GridEvidence(
        labels=["30", "90"],
        start=date(2020, 1, 1),
        end=date(2021, 12, 31),
        returns=returns,
        history=history,
    )
    settings = CpcvSettings(groups=6, test_groups=2, purge_days=1, embargo_fraction=0.01)
    return grid_report(evidence, settings, _PERIODS_PER_YEAR, pbo_blocks=16)


def test_a_grid_is_stored_as_its_choices_its_cpcv_paths_and_its_summary(tmp_path) -> None:
    grid = _grid()

    directory = write_run(tmp_path, _evidence(grid=grid, in_sample_validation="cpcv"))

    [row] = _read(directory / RUN_FILE)
    cpcv = grid.cpcv
    assert (row["in_sample_validation"], row["in_sample_passed"]) == ("cpcv", True)
    assert (row["grid_start"], row["grid_end"]) == (date(2020, 1, 1), date(2021, 12, 31))
    assert (row["grid_pbo"], row["grid_pbo_blocks"]) == (grid.pbo.pbo, 16)
    assert (row["cpcv_groups"], row["cpcv_test_groups"], row["cpcv_splits"]) == (6, 2, 15)
    assert (row["cpcv_paths"], row["cpcv_embargo"]) == (5, cpcv.embargo)
    assert row["cpcv_median_sharpe"] == cpcv.median_sharpe > 0
    assert row["cpcv_rule"] == CPCV_GATE_RULE
    assert row["configurations"] == 2

    selection = _read(directory / "selection.parquet")
    assert [(s["year"], s["position"], s["value"], s["chosen"]) for s in selection] == [
        (2020, 0, "30", False),
        (2020, 1, "90", False),
        (2021, 0, "30", False),
        (2021, 1, "90", True),
    ]
    assert selection[3]["sharpe"] == pytest.approx(0.2 * _PERIODS_PER_YEAR**0.5)  # annualized
    assert selection[0]["sharpe"] is None
    paths = _read(directory / "cpcv_paths.parquet")
    assert [path["sharpe"] for path in paths] == cpcv.path_sharpes
    choices = _read(directory / "cpcv_choices.parquet")
    assert [(c["value"], c["share"]) for c in choices] == list(cpcv.choice_shares.items())


def test_a_run_without_a_grid_has_null_grid_columns_and_empty_grid_tables(tmp_path) -> None:
    directory = write_run(tmp_path, _evidence())

    [row] = _read(directory / RUN_FILE)
    assert row["in_sample_validation"] == "walk_forward"
    assert row["in_sample_passed"] == row["walk_forward_passed"]
    for column in ("grid_start", "grid_pbo", "cpcv_groups", "cpcv_median_sharpe", "cpcv_rule"):
        assert row[column] is None, column
    for table in ("selection", "cpcv_paths", "cpcv_choices"):
        assert _read(directory / f"{table}.parquet") == []


@pytest.mark.parametrize(("drift", "status"), [(0.0, "confirmed"), (-0.005, "rejected")])
def test_an_opened_holdout_concludes_with_the_stored_cpcv_gate(tmp_path, drift, status) -> None:
    repo = _definitions(tmp_path / "definitions")
    store = tmp_path / "results"
    # The walk-forward failed, but this run's frozen in-sample gate is the CPCV.
    evidence = _evidence(
        walk_forward=_walk_forward(False), grid=_grid(drift), in_sample_validation="cpcv"
    )
    write_run(store, evidence)
    write_holdout_record(repo / "momentum_v1.opened.json", _opened("passed"))

    rows = write_registry(store, repo)

    assert rows[0].status == status
    stored = _read(store / REGISTRY_FILE)[0]
    # The registry names each definition's gate and configurations: these are frozen before q8.
    assert (stored["in_sample_validation"], stored["configurations"]) == ("walk_forward", 1)
