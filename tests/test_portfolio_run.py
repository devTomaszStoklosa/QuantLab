"""`quantlab` commands on a portfolio of frozen hypotheses (q9-P4)."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument
from quantlab.research.definition import StrategyPortfolioParameters
from quantlab.validation.holdout import (
    parse_holdout_config,
    read_holdout_record,
    write_holdout_record,
)

_FIRST, _LAST = date(2017, 1, 1), date(2022, 12, 31)
_REPO = Path(__file__).parents[1]
_COSTS = "  cost_model: {name: realistic, fee_bps: 10, k: 0.05, vol_window: 30}\n"
_PERIODS = """training_start: 2018-01-01
training_end: 2021-12-31
start: 2022-06-01
end: 2022-12-31
"""
_CRITERION = """success_criterion:
  description: test
  min_sharpe: 0.0
  max_p_value: 0.1
"""
_COMPONENTS = {
    "mom_v1": "  strategy: time_series_momentum\n  lookback_days: 60\n",
    "rev_v1": "  strategy: short_term_reversal\n  formation_days: 7\n",
}
_PORTFOLIO = """  strategy: strategy_portfolio
  components: [mom_v1, rev_v1]
  allocation: inverse_volatility
  window_days: 90
  min_window_days: 60
  history_start: 2017-06-01
"""


def _definition(hypothesis: str, strategy: str, universe: str = "mvp-crypto") -> str:
    return (
        f"hypothesis: {hypothesis}\n{_PERIODS}parameters:\n{strategy}"
        f"  universe: {universe}\n{_COSTS}{_CRITERION}"
    )


class _Trends(WithoutEvents):
    """BTC and ETH with trends that turn every 90 days, from 2017 to 2022."""

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


def _committed(tmp_path: Path, monkeypatch, portfolio: str = _PORTFOLIO) -> Path:
    repo = tmp_path / "definitions"
    repo.mkdir()
    _git(repo, "init", "-q")
    for hypothesis, strategy in [*_COMPONENTS.items(), ("port_v1", portfolio)]:
        (repo / f"{hypothesis}.yaml").write_text(
            _definition(hypothesis, strategy), encoding="utf-8", newline="\n"
        )
        _git(repo, "add", f"{hypothesis}.yaml")
        _git(repo, "commit", "-q", "-m", f"freeze {hypothesis}")
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", tmp_path / "results")
    monkeypatch.setitem(cli._PROVIDERS, "binance", _Trends)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    return repo


def test_run_trades_the_portfolio_of_the_frozen_components(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["run", "port_v1"])

    assert result.exit_code == 0, result.output
    assert "strategy_portfolio" in result.output
    assert "'components': ['mom_v1', 'rev_v1']" in result.output
    # A trial on the same data as its components, with one configuration.
    trials = next(line for line in result.output.splitlines() if line.startswith("Trials on"))
    assert trials.startswith("Trials on this universe and training period: 3 (")
    assert set(trials.split("(", 1)[1].rstrip(")").split(", ")) == {"mom_v1", "rev_v1", "port_v1"}
    assert "best of 3 no-edge trials" in result.output


def test_both_engines_trade_the_portfolio_alike(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["compare-engines", "port_v1"])

    assert result.exit_code == 0, result.output
    parity = next(line for line in result.output.splitlines() if line.startswith("Parity"))
    assert "numerical noise only" in parity


def test_trials_run_the_portfolio_from_its_components(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["trials", "port_v1"])

    assert result.exit_code == 0, result.output
    assert "port_v1" in result.output
    assert "Threshold = expected best Sharpe of 3 no-edge trials" in result.output


def test_the_holdout_waits_for_the_components_overlapping_holdouts(tmp_path, monkeypatch) -> None:
    repo = _committed(tmp_path, monkeypatch)

    refused = CliRunner().invoke(cli.app, ["open-holdout", "port_v1"])

    assert refused.exit_code == 1
    assert "overlaps the unopened holdouts of mom_v1, rev_v1; open them first" in refused.output
    assert not (repo / "port_v1.opened.json").exists()

    template = read_holdout_record(_REPO / "config" / "holdout" / "momentum_v1.opened.json")
    for component in _COMPONENTS:
        write_holdout_record(
            repo / f"{component}.opened.json", template.model_copy(update={"hypothesis": component})
        )
    opened = CliRunner().invoke(cli.app, ["open-holdout", "port_v1"])

    assert opened.exit_code == 0, opened.output
    assert read_holdout_record(repo / "port_v1.opened.json").hypothesis == "port_v1"


def test_a_component_changed_after_freezing_stops_the_run(tmp_path, monkeypatch) -> None:
    repo = _committed(tmp_path, monkeypatch)
    (repo / "rev_v1.yaml").write_text(
        _definition("rev_v1", "  strategy: short_term_reversal\n  formation_days: 5\n"),
        encoding="utf-8",
    )

    result = CliRunner().invoke(cli.app, ["run", "port_v1"])

    assert result.exit_code == 1
    assert "rev_v1.yaml has uncommitted changes" in result.output


def _parameters(**changes) -> StrategyPortfolioParameters:
    fields = {
        "strategy": "strategy_portfolio",
        "components": ["mom_v1", "rev_v1"],
        "allocation": "inverse_volatility",
        "window_days": 90,
        "min_window_days": 60,
        "history_start": date(2017, 6, 1),
        "universe": "mvp-crypto",
        "cost_model": {"name": "realistic", "fee_bps": 10, "k": 0.05, "vol_window": 30},
    } | changes
    return StrategyPortfolioParameters(**fields)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"components": ["mom_v1"]}, "at least 2"),
        ({"components": ["mom_v1", "mom_v1"]}, "must not repeat"),
        ({"allocation": "minimum_variance"}, "Unknown allocation 'minimum_variance'"),
        ({"window_days": 1}, "greater than or equal to 2"),
    ],
)
def test_the_definition_validates_its_rule(changes, message) -> None:
    with pytest.raises(ValidationError, match=message):
        _parameters(**changes)


def _loader(tmp_path: Path, definitions: dict[str, str]):
    configs = {}
    for hypothesis, text in definitions.items():
        path = tmp_path / f"{hypothesis}.yaml"
        path.write_text(text, encoding="utf-8")
        configs[hypothesis] = parse_holdout_config(path)
    return configs.__getitem__


def test_components_must_share_the_universe_and_not_be_portfolios(tmp_path) -> None:
    other = _loader(
        tmp_path,
        {
            "mom_v1": _definition("mom_v1", _COMPONENTS["mom_v1"], universe="demo-equities"),
            "rev_v1": _definition("rev_v1", _COMPONENTS["rev_v1"]),
        },
    )
    nested = _loader(
        tmp_path,
        {
            "mom_v1": _definition("mom_v1", _PORTFOLIO),
            "rev_v1": _definition("rev_v1", _COMPONENTS["rev_v1"]),
        },
    )

    with pytest.raises(ValueError, match="Component mom_v1 trades demo-equities"):
        _parameters().resolve(other)
    with pytest.raises(ValueError, match="Component mom_v1 is itself a portfolio"):
        _parameters().resolve(nested)
    with pytest.raises(ValueError, match="resolve\\(\\) it first"):
        _parameters().build_strategy()


def test_a_resolved_portfolio_fetches_every_sleeve_s_warm_up_and_counts_once(tmp_path) -> None:
    load = _loader(
        tmp_path,
        {name: _definition(name, strategy) for name, strategy in _COMPONENTS.items()},
    )

    parameters = _parameters().resolve(load)

    assert parameters.configurations == 1
    # The anchor 2017-06-01 less the momentum sleeve's 60 days.
    assert parameters.fetch_start(date(2018, 1, 1)) == date(2017, 6, 1) - timedelta(days=60)
    assert parameters.holdout_prerequisites(date(2022, 6, 1), date(2022, 12, 31)) == [
        "mom_v1",
        "rev_v1",
    ]
    assert parameters.holdout_prerequisites(date(2023, 1, 1), date(2023, 6, 30)) == []
    assert parameters.build_strategy().history is parameters.build_strategy().history
