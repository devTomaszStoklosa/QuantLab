import importlib.metadata
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pytest
from typer.testing import CliRunner

from quantlab import cli
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.cli import app, run_cost_comparison, run_engine_comparison, run_study
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument, Universe
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.research.definition import (
    CostModelParameters,
    ShortTermReversalParameters,
    TimeSeriesMomentumParameters,
)
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.validation.holdout import read_holdout_record, write_holdout_record

runner = CliRunner()

_PARAMETERS = TimeSeriesMomentumParameters(
    strategy="time_series_momentum",
    lookback_days=2,
    universe="test-universe",
    cost_model=CostModelParameters(name="realistic", fee_bps=10, k=0.05, vol_window=30),
)
_HOLDOUT_DIR = Path(__file__).parents[1] / "config" / "holdout"

_FIRST_DAY = date(2026, 1, 1)
_CLOSES = {
    "a": [100.0, 101.0, 102.0, 103.0, 104.0],
    "b": [100.0, 99.0, 98.0, 97.0, 96.0],
}
_UNIVERSE = Universe(
    name="test-universe",
    asof_date=_FIRST_DAY,
    source="binance",
    periods_per_year=365,
    instruments=[
        Instrument(id="a", symbol="AUSDT", asset_class="crypto", quote_asset="USDT"),
        Instrument(id="b", symbol="BUSDT", asset_class="crypto", quote_asset="USDT"),
    ],
)


class _FixtureProvider(WithoutEvents):
    """DataProvider test double: serves fixed daily closes, records each request."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, date, date]] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.requests.append((instrument.id, start, end))
        bars = []
        for offset, close in enumerate(_CLOSES[instrument.id]):
            ts = _FIRST_DAY + timedelta(days=offset)
            if start <= ts <= end:
                bars.append(
                    PriceBar(
                        instrument_id=instrument.id,
                        ts=ts,
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        volume=1.0,
                        adj_close=None,
                        source="test",
                    )
                )
        return bars


def test_version_flag_prints_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert importlib.metadata.version("quantlab") in result.stdout


def test_run_study_fetches_warm_up_history_and_nothing_after_end() -> None:
    provider = _FixtureProvider()
    start, end = date(2026, 1, 3), date(2026, 1, 5)

    run_study(
        provider=provider,
        parameters=_PARAMETERS,
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        start=start,
        end=end,
        seed=0,
        git_sha="abc123",
    )

    assert provider.requests == [("a", date(2026, 1, 1), end), ("b", date(2026, 1, 1), end)]


def test_run_study_uses_warm_up_history_for_first_window_signal() -> None:
    start, end = date(2026, 1, 3), date(2026, 1, 5)

    result = run_study(
        provider=_FixtureProvider(),
        parameters=_PARAMETERS,
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        start=start,
        end=end,
        seed=0,
        git_sha="abc123",
    )

    assert [snapshot.ts for snapshot in result.snapshots] == [
        date(2026, 1, 3),
        date(2026, 1, 4),
        date(2026, 1, 5),
    ]
    # Signal as-of the window's first day needs the two warm-up bars before it.
    assert result.snapshots[1].positions == {"a": 0.5, "b": -0.5}


def test_run_study_records_run_metadata() -> None:
    result = run_study(
        provider=_FixtureProvider(),
        parameters=_PARAMETERS,
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        start=date(2026, 1, 3),
        end=date(2026, 1, 5),
        seed=7,
        git_sha="abc123",
    )

    assert result.universe_name == "test-universe"
    assert result.strategy_name == "time_series_momentum"
    assert result.strategy_params == {"lookback_days": 2}
    assert result.seed == 7
    assert result.git_sha == "abc123"


def test_run_study_equals_the_engine_run_it_replaced() -> None:
    """REQ-302: the generalized runner adds nothing to a momentum run."""
    provider = _FixtureProvider()
    cost_model = NaiveCostModel(bps=100)
    start, end = date(2026, 1, 3), date(2026, 1, 5)

    result = run_study(provider, _PARAMETERS, cost_model, _UNIVERSE, start, end, 0, "abc123")

    bars = {
        instrument.id: provider.fetch(instrument, date(2026, 1, 1), end)
        for instrument in _UNIVERSE.instruments
    }
    expected = run_backtest(
        strategy=TimeSeriesMomentum(lookback_days=2),
        cost_model=cost_model,
        bars=bars,
        universe_name="test-universe",
        start=start,
        end=end,
        seed=0,
        git_sha="abc123",
        strategy_name="time_series_momentum",
        strategy_params={"lookback_days": 2},
    )
    assert result.snapshots == expected.snapshots
    assert result.model_dump(exclude={"id"}) == expected.model_dump(exclude={"id"})


def test_run_study_builds_the_strategy_its_parameters_name() -> None:
    reversal = ShortTermReversalParameters(
        strategy="short_term_reversal",
        formation_days=1,
        universe="test-universe",
        cost_model=_PARAMETERS.cost_model,
    )

    result = run_study(
        _FixtureProvider(),
        reversal,
        ZeroCostModel(),
        _UNIVERSE,
        date(2026, 1, 3),
        date(2026, 1, 5),
        0,
        "abc123",
    )

    assert result.strategy_name == "short_term_reversal"
    assert result.strategy_params == {"formation_days": 1}
    # "a" rose and "b" fell the day before: reversal takes the opposite of momentum's side.
    assert result.snapshots[1].positions == {"a": -0.5, "b": 0.5}


def test_run_cost_comparison_fetches_once_and_runs_each_model() -> None:
    provider = _FixtureProvider()

    runs = run_cost_comparison(
        provider=provider,
        parameters=_PARAMETERS,
        cost_models=[ZeroCostModel(), NaiveCostModel(bps=100)],
        universe=_UNIVERSE,
        start=date(2026, 1, 3),
        end=date(2026, 1, 5),
        seed=0,
        git_sha="abc123",
    )

    assert [instrument_id for instrument_id, _, _ in provider.requests] == ["a", "b"]
    assert [run.cost_model_name for run in runs] == ["zero-cost", "naive-100bps"]
    # Same signals and prices; only costs differ, so the costlier run ends lower.
    assert runs[1].snapshots[-1].equity < runs[0].snapshots[-1].equity


class _RandomWalkProvider(WithoutEvents):
    """DataProvider test double: a seeded random walk per instrument, records requests."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, date, date]] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.requests.append((instrument.id, start, end))
        rng = np.random.default_rng(len(instrument.id) + ord(instrument.id[0]))
        returns = rng.normal(0.0005, 0.03, (end - start).days + 1)
        closes = 100.0 * np.cumprod(1.0 + returns)
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=start + timedelta(days=i),
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


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _definition_repo(repo: Path, monkeypatch) -> _RandomWalkProvider:
    """momentum_v1's real definition with a 2022-2023 training period, committed in
    a temporary repo that `quantlab run` reads definitions from; returns the provider
    the command will use.
    """
    text = (_HOLDOUT_DIR / "momentum_v1.yaml").read_text(encoding="utf-8")
    assert "training_start: 2018-01-01" in text
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "momentum_v1.yaml").write_text(
        text.replace("training_start: 2018-01-01", "training_start: 2022-01-01"), encoding="utf-8"
    )
    _git(repo, "add", "momentum_v1.yaml")
    _git(repo, "commit", "-q", "-m", "freeze")
    provider = _RandomWalkProvider()
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setitem(cli._PROVIDERS, "binance", lambda: provider)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    return provider


def test_run_takes_the_hypothesis_from_its_committed_definition(tmp_path, monkeypatch) -> None:
    provider = _definition_repo(tmp_path / "definitions", monkeypatch)
    output = tmp_path / "reports" / "tear-sheet.html"

    result = runner.invoke(app, ["run", "momentum_v1", "--tear-sheet", str(output)])

    assert result.exit_code == 0, result.output
    # Warm-up of lookback_days before the definition's training start, nothing after its end.
    assert set(provider.requests) == {
        ("btc-usdt", date(2021, 1, 1), date(2023, 12, 31)),
        ("eth-usdt", date(2021, 1, 1), date(2023, 12, 31)),
    }
    assert "Strategy:       time_series_momentum {'lookback_days': 365}" in result.output
    assert f"Tear-sheet written to {output}" in result.output
    page = output.read_text(encoding="utf-8")
    assert "<h1>momentum_v1</h1>" in page
    assert "Okres treningowy 2022-01-01 \u2192 2023-12-31" in page
    assert "realistic-10bps-k0.05-vol30d</code> *" in page
    assert "nie został jeszcze otwarty" in page
    assert "Hypothesis momentum_v1: no verdict until the frozen holdout is opened" in result.output
    # The temporary repo holds one committed definition, so there is one trial.
    assert "Trials on this universe and training period: 1 (momentum_v1)" in result.output
    assert '<h3 id="multiple-testing">' in page
    # Crypto's calendar: a month and a year of daily sessions (REQ-506).
    assert "btc-usdt 30-session volatility tercile vs its last 365 sessions" in result.output


def test_run_refuses_a_universe_whose_data_source_is_unknown(tmp_path, monkeypatch) -> None:
    provider = _definition_repo(tmp_path / "definitions", monkeypatch)
    monkeypatch.delitem(cli._PROVIDERS, "binance")

    result = runner.invoke(app, ["run", "momentum_v1"])

    assert result.exit_code == 1
    assert "names data source 'binance'; known sources:" in result.output
    assert provider.requests == []


def test_run_before_the_sp500_universe_is_built_says_how_to_build_it(tmp_path, monkeypatch) -> None:
    provider = _definition_repo(tmp_path / "definitions", monkeypatch)
    definition = tmp_path / "definitions" / "momentum_v1.yaml"
    definition.write_text(
        definition.read_text(encoding="utf-8").replace("universe: mvp-crypto", "universe: sp500"),
        encoding="utf-8",
    )
    _git(tmp_path / "definitions", "commit", "-q", "-am", "equities")

    def not_built(cls, name: str) -> Universe:
        raise ValueError(f"Universe '{name}' not found")

    monkeypatch.setattr(Universe, "load", classmethod(not_built))

    result = runner.invoke(app, ["run", "momentum_v1"])

    assert result.exit_code == 1
    assert "Universe 'sp500' not found - build it with `uv run quantlab build-universe`" in (
        result.output
    )
    assert provider.requests == []


def test_the_regime_windows_are_a_month_and_a_year_of_the_universes_sessions() -> None:
    crypto = Universe.load("mvp-crypto")
    equities = crypto.model_copy(update={"periods_per_year": 252})

    assert cli._regime_windows(crypto) == (30, 365)
    assert cli._regime_windows(equities) == (21, 252)


def test_run_reports_the_status_from_the_recorded_holdout(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    _definition_repo(repo, monkeypatch)
    record = read_holdout_record(_HOLDOUT_DIR / "momentum_v1.opened.json")
    write_holdout_record(repo / "momentum_v1.opened.json", record)
    output = tmp_path / "tear-sheet.html"

    result = runner.invoke(app, ["run", "--tear-sheet", str(output)])

    assert result.exit_code == 0, result.output
    # The recorded holdout is inconclusive, so no walk-forward result can make it confirmed.
    status_line = next(
        line for line in result.output.splitlines() if line.startswith("Hypothesis momentum_v1:")
    )
    assert "holdout inconclusive as recorded 2026-09-23" in status_line
    assert "CONFIRMED" not in status_line
    page = output.read_text(encoding="utf-8")
    assert "0.37" in page[page.index('<section id="holdout"') :]


def test_run_refuses_an_uncommitted_definition_before_fetching(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)
    definition = repo / "momentum_v1.yaml"
    definition.write_text(
        definition.read_text(encoding="utf-8").replace("lookback_days: 365", "lookback_days: 180"),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["run", "momentum_v1"])

    assert result.exit_code == 1
    assert "uncommitted changes" in result.output
    assert provider.requests == []


def test_run_refuses_an_undefined_hypothesis(tmp_path, monkeypatch) -> None:
    provider = _definition_repo(tmp_path / "definitions", monkeypatch)

    result = runner.invoke(app, ["run", "no_such_v1"])

    assert result.exit_code == 1
    assert "No frozen holdout file" in result.output
    assert provider.requests == []


def test_run_contrasts_with_another_hypothesis(tmp_path, monkeypatch) -> None:
    _definition_repo(tmp_path / "definitions", monkeypatch)
    output = tmp_path / "tear-sheet.html"

    result = runner.invoke(
        app, ["run", "momentum_v1", "--contrast", "momentum_v1", "--tear-sheet", str(output)]
    )

    assert result.exit_code == 0, result.output
    # A hypothesis contrasted with itself moves in lockstep.
    assert "on days both held a position +1.00" in result.output
    assert "Turnover" in result.output
    assert '<h3 id="contrast">' in output.read_text(encoding="utf-8")


def test_run_refuses_an_undefined_contrast_before_fetching(tmp_path, monkeypatch) -> None:
    provider = _definition_repo(tmp_path / "definitions", monkeypatch)

    result = runner.invoke(app, ["run", "momentum_v1", "--contrast", "no_such_v1"])

    assert result.exit_code == 1
    assert "No frozen holdout file" in result.output
    assert provider.requests == []


def test_run_engine_comparison_runs_each_mode_on_one_fetch() -> None:
    provider = _RandomWalkProvider()

    comparison = run_engine_comparison(
        provider=provider,
        parameters=_PARAMETERS,
        universe=_UNIVERSE,
        start=date(2026, 1, 10),
        end=date(2026, 4, 30),
        seed=0,
        git_sha="abc123",
        capital=100_000.0,
        max_participation=0.025,
    )

    assert provider.requests == [
        ("a", date(2026, 1, 8), date(2026, 4, 30)),
        ("b", date(2026, 1, 8), date(2026, 4, 30)),
    ]
    assert [row.label for row in comparison.rows] == [
        "vectorized, close t",
        "event-driven, close t",
        "event-driven, open t+1",
        "event-driven, close t+1",
        "event-driven, open t+1, 2.5% vol",
    ]
    assert comparison.parity_difference < 1e-12
    assert comparison.rows[0].limited_orders is None
    assert comparison.rows[1].metrics.model_dump() == pytest.approx(
        comparison.rows[0].metrics.model_dump(), rel=1e-9
    )
    # The test data trades 1 unit a day, so 100 000 of capital outgrows 2.5% of it at once.
    assert comparison.rows[4].limited_orders > 0
    assert comparison.capacity < 100_000.0
    assert all(
        row.metrics.cost_model_name == "realistic-10bps-k0.05-vol30d" for row in comparison.rows
    )


def test_compare_engines_reads_the_training_period_only(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)

    result = runner.invoke(app, ["compare-engines", "momentum_v1"])

    assert result.exit_code == 0, result.output
    assert set(provider.requests) == {
        ("btc-usdt", date(2021, 1, 1), date(2023, 12, 31)),
        ("eth-usdt", date(2021, 1, 1), date(2023, 12, 31)),
    }
    assert "Period:         2022-01-01 .. 2023-12-31 (training only)" in result.output
    for label in ("vectorized, close t", "event-driven, open t+1", "event-driven, close t+1"):
        assert label in result.output
    assert "numerical noise only" in result.output
    assert "Capacity (event-driven, open t+1): the 2.5% volume limit" in result.output
    assert not (repo / "momentum_v1.opened.json").exists()


def test_compare_engines_refuses_an_uncommitted_definition_before_fetching(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)
    (repo / "momentum_v1.yaml").write_text("changed", encoding="utf-8")

    result = runner.invoke(app, ["compare-engines", "momentum_v1"])

    assert result.exit_code == 1
    assert "uncommitted changes" in result.output
    assert provider.requests == []


def _add_definition(repo: Path, hypothesis: str, strategy_lines: str) -> None:
    """A second hypothesis on momentum_v1's data, committed next to it."""
    text = (repo / "momentum_v1.yaml").read_text(encoding="utf-8")
    text = text.replace("hypothesis: momentum_v1", f"hypothesis: {hypothesis}").replace(
        "  strategy: time_series_momentum\n  lookback_days: 365\n", strategy_lines
    )
    assert f"hypothesis: {hypothesis}" in text and strategy_lines in text
    (repo / f"{hypothesis}.yaml").write_text(text, encoding="utf-8")
    _git(repo, "add", f"{hypothesis}.yaml")
    _git(repo, "commit", "-q", "-m", f"freeze {hypothesis}")


_REVERSAL = "  strategy: short_term_reversal\n  formation_days: 7\n"


def test_trials_deflates_each_trial_and_reports_pbo(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)
    _add_definition(repo, "reversal_v1", _REVERSAL)

    result = runner.invoke(app, ["trials", "momentum_v1"])

    assert result.exit_code == 0, result.output
    assert "overlapping momentum_v1's (2022-01-01 .. 2023-12-31): 2" in result.output
    rows = [line.split()[0] for line in result.output.splitlines()[2:4]]
    assert rows == ["momentum_v1", "reversal_v1"]
    assert "PBO of picking the best trial in-sample:" in result.output
    assert "12,870 splits" in result.output
    # Each trial fetches its own training period with its own warm-up, nothing later.
    assert set(provider.requests) == {
        ("btc-usdt", date(2021, 1, 1), date(2023, 12, 31)),
        ("eth-usdt", date(2021, 1, 1), date(2023, 12, 31)),
        ("btc-usdt", date(2021, 12, 25), date(2023, 12, 31)),
        ("eth-usdt", date(2021, 12, 25), date(2023, 12, 31)),
    }


def test_trials_keeps_a_deleted_definition(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    _definition_repo(repo, monkeypatch)
    _add_definition(repo, "abandoned_v1", _REVERSAL)
    (repo / "abandoned_v1.yaml").unlink()
    _git(repo, "commit", "-q", "-am", "drop abandoned_v1")

    result = runner.invoke(app, ["trials", "momentum_v1"])

    assert result.exit_code == 0, result.output
    assert "abandoned_v1*" in result.output
    assert "* definition deleted since" in result.output


def test_trials_with_one_trial_has_no_pbo(tmp_path, monkeypatch) -> None:
    _definition_repo(tmp_path / "definitions", monkeypatch)

    result = runner.invoke(app, ["trials"])

    assert result.exit_code == 0, result.output
    assert "PBO: n/a (needs at least 2 trials)" in result.output


def test_trials_refuses_an_edited_trial_before_fetching(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)
    _add_definition(repo, "reversal_v1", _REVERSAL)
    edited = repo / "reversal_v1.yaml"
    edited.write_text(
        edited.read_text(encoding="utf-8").replace("formation_days: 7", "formation_days: 3"),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["trials", "momentum_v1"])

    assert result.exit_code == 1
    assert "reversal_v1.yaml has uncommitted changes" in result.output
    assert provider.requests == []


_IDLE_PAIRS = (
    "  strategy: pairs_spread\n  dependent: eth-usdt\n  explanatory: btc-usdt\n"
    "  formation_days: 365\n  entry_z: 2.0\n  exit_z: 0.0\n  max_coint_p_value: 0.000000000001\n"
)


def test_run_reports_a_hypothesis_that_never_trades(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    _definition_repo(repo, monkeypatch)
    _add_definition(repo, "idle_v1", _IDLE_PAIRS)
    output = tmp_path / "idle.html"

    result = runner.invoke(app, ["run", "idle_v1", "--tear-sheet", str(output)])

    assert result.exit_code == 0, result.output
    assert "First position: None" in result.output
    assert "-> undefined: no Sharpe to compare" in result.output
    assert "n/a: no positions were held" in result.output
    assert "0 trades (0 open at the end), n/a with net P&L > 0" in result.output
    assert output.exists()


_PAIRS = (
    "  strategy: pairs_spread\n  dependent: eth-usdt\n  explanatory: btc-usdt\n"
    "  formation_days: 365\n  entry_z: 2.0\n  exit_z: 0.0\n  max_coint_p_value: 0.05\n"
)


def test_run_reports_cointegration_for_a_pairs_hypothesis(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    _definition_repo(repo, monkeypatch)
    _add_definition(repo, "pairs_x", _PAIRS)

    result = runner.invoke(app, ["run", "pairs_x"])

    assert result.exit_code == 0, result.output
    assert (
        "Cointegration of eth-usdt on btc-usdt (training 2022-01-01 .. 2023-12-31):"
        in result.output
    )
    assert "hedge ratio" in result.output and "p-value" in result.output
    assert "Trials on this universe and training period: 2 (momentum_v1, pairs_x)" in result.output


def test_run_reports_no_cointegration_for_a_directional_hypothesis(tmp_path, monkeypatch) -> None:
    _definition_repo(tmp_path / "definitions", monkeypatch)

    result = runner.invoke(app, ["run", "momentum_v1"])

    assert result.exit_code == 0, result.output
    assert "Cointegration" not in result.output


def test_run_writes_its_evidence_and_the_registry_to_the_results_store(
    tmp_path, monkeypatch
) -> None:
    repo = tmp_path / "definitions"
    _definition_repo(repo, monkeypatch)
    _add_definition(repo, "pairs_x", _PAIRS)

    result = runner.invoke(app, ["run", "pairs_x"])

    assert result.exit_code == 0, result.output
    store = cli._RESULTS_DIR
    assert f"Results written to {store / 'pairs_x'}" in result.output
    [run] = pq.read_table(store / "pairs_x" / "run.parquet").to_pylist()
    assert run["data_source"] == "test"
    assert run["trials"] == ["momentum_v1", "pairs_x"]
    diagnostics = pq.read_table(store / "pairs_x" / "diagnostics.parquet").to_pylist()
    assert {row["title"] for row in diagnostics} == {"Cointegration of eth-usdt on btc-usdt"}
    registry = pq.read_table(store / "hypotheses.parquet").to_pylist()
    assert [(row["hypothesis"], row["status"]) for row in registry] == [
        ("momentum_v1", "proposed"),
        ("pairs_x", "testing"),
    ]


def test_registry_lists_the_committed_definitions_without_fetching(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    provider = _definition_repo(repo, monkeypatch)
    record = read_holdout_record(_HOLDOUT_DIR / "momentum_v1.opened.json")
    write_holdout_record(repo / "momentum_v1.opened.json", record)
    _add_definition(repo, "reversal_v1", _REVERSAL)

    result = runner.invoke(app, ["registry"])

    assert result.exit_code == 0, result.output
    assert provider.requests == []
    lines = result.output.splitlines()
    assert lines[1].split() == [
        "momentum_v1",
        "inconclusive",
        "no",
        "opened",
        "2026-09-23:",
        "inconclusive",
    ]
    assert lines[2].split() == ["reversal_v1", "proposed", "no", "sealed", "2024-01-01..2025-12-31"]
    assert f"Registry written to {cli._RESULTS_DIR / 'hypotheses.parquet'}" in result.output


def test_registry_refuses_definitions_outside_git(tmp_path, monkeypatch) -> None:
    directory = tmp_path / "not-a-repo"
    directory.mkdir()
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", directory)

    result = runner.invoke(app, ["registry"])

    assert result.exit_code == 1
    assert "Error: git log" in result.output
