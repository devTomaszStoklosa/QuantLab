import importlib.metadata
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from quantlab import cli
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.cli import app, run_cost_comparison, run_study
from quantlab.core.data.provider import PriceBar
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
    instruments=[
        Instrument(id="a", symbol="AUSDT", asset_class="crypto", quote_asset="USDT"),
        Instrument(id="b", symbol="BUSDT", asset_class="crypto", quote_asset="USDT"),
    ],
)


class _FixtureProvider:
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


class _RandomWalkProvider:
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
    monkeypatch.setattr(cli, "BinanceProvider", lambda: provider)
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
