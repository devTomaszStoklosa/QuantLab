"""`quantlab plan` on a repository of committed definitions (q10)."""

import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
import requests
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument
from quantlab.research.plan import Step

_DEFINITION = """hypothesis: {hypothesis}
training_start: 2018-01-01
training_end: 2021-12-31
start: 2022-06-01
end: 2022-12-31
parameters:
{strategy}  universe: mvp-crypto
  cost_model: {{name: realistic, fee_bps: 10, k: 0.05, vol_window: 30}}
success_criterion:
  description: test
  min_sharpe: 0.0
  max_p_value: 0.1
"""
_DEFINITIONS = {
    "mom_v1": "  strategy: time_series_momentum\n  lookback_days: 60\n",
    "rev_v1": "  strategy: short_term_reversal\n  formation_days: 7\n",
    "port_v1": (
        "  strategy: strategy_portfolio\n  components: [mom_v1, rev_v1]\n"
        "  allocation: inverse_volatility\n  window_days: 90\n  min_window_days: 60\n"
        "  history_start: 2017-06-01\n"
    ),
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    repo = tmp_path / "definitions"
    repo.mkdir()
    _git(repo, "init", "-q")
    for hypothesis, strategy in _DEFINITIONS.items():
        (repo / f"{hypothesis}.yaml").write_text(
            _DEFINITION.format(hypothesis=hypothesis, strategy=strategy),
            encoding="utf-8",
            newline="\n",
        )
        _git(repo, "add", f"{hypothesis}.yaml")
        _git(repo, "commit", "-q", "-m", f"freeze {hypothesis}")
    log = tmp_path / "RESEARCH_LOG.md"
    log.write_text("# Dziennik\n\n## Wpisy\n", encoding="utf-8")
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(cli, "_RESEARCH_LOG", log)
    monkeypatch.setattr(shutil, "which", lambda name: None)  # no dotnet: the check is blocked
    return repo


def _steps() -> dict[str, Step]:
    return {step.key: step for step in cli._plan()}


def test_plan_shows_every_step_with_its_state_and_command(repo) -> None:
    result = CliRunner().invoke(cli.app, ["plan"])

    assert result.exit_code == 0, result.output
    assert "Plan: 5 pending" in result.output
    assert "$ uv run quantlab run port_v1 --tear-sheet reports/port_v1.html" in result.output
    assert "waits for train:mom_v1" in result.output
    assert "$ uv run quantlab open-holdout" not in result.output  # blocked, not yet a command


def test_run_takes_the_checks_and_training_runs_in_order_and_no_manual_step(
    repo, monkeypatch
) -> None:
    executed: list[list[str]] = []
    monkeypatch.setattr(cli, "_EXECUTOR", lambda command: executed.append(command) or 0)
    # Registration order (commits within one second tie on time, so read it from the plan).
    runs = [step.command for step in cli._plan() if step.key.startswith("train:")]

    result = CliRunner().invoke(cli.app, ["plan", "--run"])

    assert result.exit_code == 0, result.output
    assert executed == [
        ["pytest", "-q", "tests/test_environment.py"],
        ["quantlab", "check-source", "binance"],
        *runs,
    ]
    assert sorted(command[2] for command in runs) == ["mom_v1", "port_v1", "rev_v1"]
    assert "Left for you (quantlab never takes these steps):" in result.output


def test_run_stops_at_the_first_failing_step(repo, monkeypatch) -> None:
    executed: list[list[str]] = []

    def executor(command: list[str]) -> int:
        executed.append(command)
        return 1 if command[:2] == ["quantlab", "check-source"] else 0

    monkeypatch.setattr(cli, "_EXECUTOR", executor)

    result = CliRunner().invoke(cli.app, ["plan", "--run"])

    assert result.exit_code == 1
    assert "Stopped: check:binance failed (exit code 1)." in result.output
    assert [command[:2] for command in executed] == [
        ["pytest", "-q"],
        ["quantlab", "check-source"],
    ]


def test_a_manual_step_is_refused_by_the_runner() -> None:
    step = Step(
        key="holdout:x",
        title="Open",
        kind="manual",
        state="pending",
        command=["quantlab", "open-holdout", "x"],
    )

    with pytest.raises(ValueError, match="manual step: quantlab never takes it"):
        cli.run_step(step, lambda command: 0)


def test_an_opening_record_needs_a_commit(repo) -> None:
    record = repo / "mom_v1.opened.json"
    record.write_text("{}", encoding="utf-8")

    untracked = _steps()
    _git(repo, "add", record.name)
    _git(repo, "commit", "-q", "-m", "record")
    committed = _steps()

    assert untracked["holdout:mom_v1"].state == "done"
    assert (untracked["commit:mom_v1"].state, committed["commit:mom_v1"].state) == (
        "pending",
        "done",
    )
    # The portfolio still waits for its other component.
    assert committed["holdout:port_v1"].state == "blocked"


def test_check_source_reports_what_did_not_answer(monkeypatch) -> None:
    def refuse() -> None:
        raise requests.ConnectionError("blocked by the proxy")

    monkeypatch.setitem(cli._SOURCE_CHECKS, "binance", refuse)

    failed = CliRunner().invoke(cli.app, ["check-source", "binance"])
    unknown = CliRunner().invoke(cli.app, ["check-source", "kraken"])

    assert failed.exit_code == 1
    assert "binance: not reachable - blocked by the proxy" in failed.output
    assert unknown.exit_code == 1
    assert "unknown source kraken" in unknown.output


class _Walk(WithoutEvents):
    """BTC and ETH random walks from 2017 to 2022."""

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        first = date(2017, 1, 1)
        seed = 1 if instrument.id == "btc-usdt" else 2
        closes = 100.0 * np.cumprod(1.0 + np.random.default_rng(seed).normal(0.0, 0.02, 2191))
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=first + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(closes)
            if start <= first + timedelta(days=i) <= end
        ]


def test_a_run_is_done_until_a_new_trial_on_its_data_makes_it_stale(repo, monkeypatch) -> None:
    monkeypatch.setitem(cli._PROVIDERS, "binance", _Walk)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    ran = CliRunner().invoke(cli.app, ["run", "mom_v1"])
    assert ran.exit_code == 0, ran.output

    before = _steps()
    (repo / "new_v1.yaml").write_text(
        _DEFINITION.format(hypothesis="new_v1", strategy=_DEFINITIONS["mom_v1"]),
        encoding="utf-8",
        newline="\n",
    )
    _git(repo, "add", "new_v1.yaml")
    _git(repo, "commit", "-q", "-m", "freeze new_v1")
    after = _steps()

    assert before["train:mom_v1"].state == "done"
    assert before["holdout:mom_v1"].state == "pending"  # trained: the researcher may open it
    assert (after["train:mom_v1"].state, after["train:mom_v1"].reason) == (
        "pending",
        "new trials on its data: new_v1",
    )
