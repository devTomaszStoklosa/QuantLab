"""`quantlab run` on a hypothesis that chooses its parameter from a grid (q8)."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument, Universe
from quantlab.research.trials import registered_trials, trials_on_same_data
from quantlab.validation.cpcv import CpcvSettings
from quantlab.validation.holdout import (
    HoldoutConfig,
    SuccessCriterion,
    parse_holdout_config,
    read_holdout_record,
    write_holdout_record,
)

_FIRST, _LAST = date(2016, 1, 1), date(2022, 12, 31)
_REPO = Path(__file__).parents[1]
_DEFINITION = """hypothesis: select_v1
training_start: 2018-01-01
training_end: 2021-12-31
start: 2022-06-01
end: 2022-12-31
parameters:
  strategy: time_series_momentum_selected
  lookback_grid: [30, 90, 180]
  history_start: 2017-01-01
  min_history_days: 365
  universe: mvp-crypto
  cost_model: {name: realistic, fee_bps: 10, k: 0.05, vol_window: 30}
success_criterion:
  description: test
  min_sharpe: 0.0
  max_p_value: 0.1
  in_sample_validation: cpcv
  cpcv: {groups: 6, test_groups: 2, purge_days: 1, embargo_fraction: 0.01}
"""


class _Trends(WithoutEvents):
    """BTC and ETH with trends that turn every 90 days, from 2016 to 2022."""

    def __init__(self) -> None:
        rng = np.random.default_rng(42)
        days = (_LAST - _FIRST).days + 1
        drift = np.repeat(rng.choice([-0.004, 0.004], size=days // 90 + 1), 90)[:days]
        self.closes = {
            instrument_id: 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.02, days))
            for instrument_id in ("btc-usdt", "eth-usdt")
        }

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_FIRST + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1.0,
                source="test",
            )
            for i, close in enumerate(self.closes[instrument.id])
            if start <= _FIRST + timedelta(days=i) <= end
        ]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _committed(tmp_path: Path, monkeypatch) -> Path:
    repo = tmp_path / "definitions"
    repo.mkdir()
    (repo / "select_v1.yaml").write_text(_DEFINITION, encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "select_v1.yaml")
    _git(repo, "commit", "-q", "-m", "freeze")
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setitem(cli._PROVIDERS, "binance", _Trends)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    return repo


def test_run_reports_the_choices_the_pbo_and_the_cpcv_of_the_grid(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["run", "select_v1"])

    assert result.exit_code == 0, result.output
    output = result.output
    assert "Parameter selection: grid 30, 90, 180" in output
    rows = [line.split() for line in output.splitlines() if line.split()]
    years = [row[0] for row in rows if len(row[0]) == 4 and row[0].isdigit()]
    assert years == ["2018", "2019", "2020", "2021"]
    assert "PBO of choosing from the grid (CSCV, 16 blocks" in output
    assert "CPCV of the selection (6 groups, 2 for testing, purge 1 and embargo" in output
    assert "15 splits, 5 paths" in output
    assert "In-sample gate (frozen): median Sharpe of the CPCV paths > 0" in output
    assert "Switches between a path's segments are not costed" in output
    assert "Descriptive only: this hypothesis's frozen in-sample gate is CPCV." in output
    # The grid's three lookbacks count toward the DSR threshold (REQ-820).
    assert "Trials on this universe and training period: 1 (select_v1); 3 parameter" in output
    assert "best of 3 no-edge configurations" in output


def test_the_status_takes_the_cpcv_gate(tmp_path, monkeypatch) -> None:
    repo = _committed(tmp_path, monkeypatch)
    record = read_holdout_record(_REPO / "config" / "holdout" / "momentum_v1.opened.json")
    passed = record.model_copy(update={"hypothesis": "select_v1", "verdict": "passed"})
    write_holdout_record(repo / "select_v1.opened.json", passed)

    result = CliRunner().invoke(cli.app, ["run", "select_v1"])

    assert result.exit_code == 0, result.output
    gate = next(
        line for line in result.output.splitlines() if line.startswith("In-sample gate (frozen)")
    )
    outcome = gate.rsplit("-> ", 1)[1]
    status = next(
        line for line in result.output.splitlines() if line.startswith("Hypothesis select_v1:")
    )
    assert f"(CPCV {outcome}, holdout passed" in status
    expected = {"passed": "CONFIRMED", "failed": "REJECTED", "inconclusive": "INCONCLUSIVE"}
    assert expected[outcome] in status


def test_a_cpcv_gate_needs_its_settings_and_a_grid() -> None:
    with pytest.raises(ValidationError, match="needs its frozen cpcv settings"):
        SuccessCriterion(
            description="d", min_sharpe=0.0, max_p_value=0.1, in_sample_validation="cpcv"
        )
    momentum = parse_holdout_config(_REPO / "config" / "holdout" / "momentum_v1.yaml")
    criterion = momentum.success_criterion.model_copy(
        update={
            "in_sample_validation": "cpcv",
            "cpcv": CpcvSettings(groups=10, test_groups=2, purge_days=1, embargo_fraction=0.01),
        }
    )
    with pytest.raises(ValidationError, match="needs a parameter grid"):
        HoldoutConfig.model_validate(
            momentum.model_dump() | {"success_criterion": criterion.model_dump()}
        )


def test_frozen_definitions_keep_walk_forward_as_their_gate() -> None:
    for name in ("momentum_v1", "mean_reversion_v1", "pairs_v1", "xsmom_v1"):
        config = parse_holdout_config(_REPO / "config" / "holdout" / f"{name}.yaml")
        assert config.success_criterion.in_sample_validation == "walk_forward"
        assert config.parameters.configurations == 1


def test_momentum_select_v1_freezes_the_answers_to_the_story_s_questions() -> None:
    config = parse_holdout_config(_REPO / "config" / "holdout" / "momentum_select_v1.yaml")
    parameters = config.parameters
    criterion = config.success_criterion

    assert parameters.lookback_grid == [30, 60, 90, 180, 270, 365]
    assert (parameters.history_start, parameters.min_history_days) == (date(2018, 1, 1), 365)
    assert criterion.in_sample_validation == "cpcv"
    assert criterion.cpcv == CpcvSettings(
        groups=10, test_groups=2, purge_days=1, embargo_fraction=0.01
    )
    assert criterion.significance_test == "day_shuffle"
    assert (config.training_start, config.training_end) == (date(2018, 1, 1), date(2023, 12, 31))
    assert (config.start, config.end) == (date(2026, 1, 1), date(2026, 8, 31))
    # The holdout's 2026 choice is made on all history since the anchor.
    assert parameters.fetch_start(config.start, Universe.load(parameters.universe)) == date(
        2017, 1, 1
    )
    # Its six lookbacks join the single-configuration trials on these data.
    trials = trials_on_same_data(
        "momentum_select_v1", registered_trials(_REPO / "config" / "holdout")
    )
    configurations = {t.hypothesis: t.definition.parameters.configurations for t in trials}
    assert configurations["momentum_select_v1"] == 6
    assert sum(configurations.values()) == len(trials) + 5
