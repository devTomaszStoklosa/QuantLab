"""`quantlab` commands on momentum scaled to a target volatility (q11-V3)."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument
from quantlab.reporting.volatility_scaling import CONTRAST_TITLE, SCALE_TITLE
from quantlab.research.definition import VolatilityTargetedMomentumParameters
from quantlab.research.trials import registered_trials, trials_on_same_data
from quantlab.validation.holdout import parse_holdout_config

_FIRST, _LAST = date(2017, 1, 1), date(2022, 12, 31)
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
    "vt_v1": (
        "  strategy: time_series_momentum_vol_target\n  lookback_days: 60\n"
        "  target_volatility: 0.4\n  max_scale: 1.0\n"
        "  volatility: {estimator: ewma, center_of_mass_days: 20, window_days: 60}\n"
    ),
}


class _Regimes(WithoutEvents):
    """BTC and ETH whose trends turn every 90 days and volatility every 120."""

    def __init__(self) -> None:
        rng = np.random.default_rng(8)
        days = (_LAST - _FIRST).days + 1
        drift = np.repeat(rng.choice([-0.003, 0.003], size=days // 90 + 1), 90)[:days]
        volatility = np.repeat(np.resize([0.01, 0.06, 0.03], days // 120 + 1), 120)[:days]
        self.closes = {
            instrument_id: 100.0 * np.cumprod(1.0 + drift + volatility * rng.normal(0, 1, days))
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
                volume=1e9,
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
    _git(repo, "init", "-q")
    for hypothesis, strategy in _DEFINITIONS.items():
        (repo / f"{hypothesis}.yaml").write_text(
            _DEFINITION.format(hypothesis=hypothesis, strategy=strategy),
            encoding="utf-8",
            newline="\n",
        )
        _git(repo, "add", f"{hypothesis}.yaml")
        _git(repo, "commit", "-q", "-m", f"freeze {hypothesis}")
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", tmp_path / "results")
    monkeypatch.setitem(cli._PROVIDERS, "binance", _Regimes)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    return repo


def test_run_reports_the_scales_and_the_unscaled_contrast(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["run", "vt_v1"])

    assert result.exit_code == 0, result.output
    assert "time_series_momentum_vol_target" in result.output
    trials = next(line for line in result.output.splitlines() if line.startswith("Trials on"))
    assert trials.startswith("Trials on this universe and training period: 2 (")
    assert f"{SCALE_TITLE} (training 2018-01-01 .. 2021-12-31):" in result.output
    assert f"{CONTRAST_TITLE} (training 2018-01-01 .. 2021-12-31):" in result.output
    stored = pq.read_table(tmp_path / "results" / "vt_v1" / "diagnostics.parquet").to_pylist()
    assert {row["title"] for row in stored} == {SCALE_TITLE, CONTRAST_TITLE}
    assert {row["label"] for row in stored} >= {"btc-usdt share at the cap", "Sharpe unscaled"}


def test_both_engines_trade_the_scaled_positions_alike(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["compare-engines", "vt_v1"])

    assert result.exit_code == 0, result.output
    parity = next(line for line in result.output.splitlines() if line.startswith("Parity"))
    assert "numerical noise only" in parity


def test_momentum_voltarget_v1_freezes_the_answers_to_the_story_s_questions() -> None:
    definitions = Path(__file__).parents[1] / "config" / "holdout"

    config = parse_holdout_config(definitions / "momentum_voltarget_v1.yaml")
    parameters = config.parameters
    momentum = parse_holdout_config(definitions / "momentum_v1.yaml").parameters

    assert isinstance(parameters, VolatilityTargetedMomentumParameters)
    assert (parameters.target_volatility, parameters.max_scale) == (0.40, 1.0)
    assert parameters.volatility.model_dump() == {
        "estimator": "ewma",
        "window_days": 365,
        "center_of_mass_days": 60.0,
    }
    # The only difference from momentum_v1 is the position size.
    assert parameters.lookback_days == momentum.lookback_days == 365
    assert parameters.cost_model == momentum.cost_model
    assert parameters.universe == momentum.universe
    assert parameters.warm_up_days == 365
    assert config.success_criterion.in_sample_validation == "walk_forward"
    assert (config.success_criterion.min_sharpe, config.success_criterion.max_p_value) == (
        0.0,
        0.1,
    )
    assert (config.training_start, config.training_end) == (date(2018, 1, 1), date(2023, 12, 31))
    assert (config.start, config.end) == (date(2026, 1, 1), date(2026, 8, 31))
    # A new trial on the other crypto hypotheses' data, with one configuration.
    trials = trials_on_same_data("momentum_voltarget_v1", registered_trials(definitions))
    assert {"momentum_v1", "momentum_voltarget_v1"} <= {trial.hypothesis for trial in trials}
    assert parameters.configurations == 1
