"""`quantlab` commands on the frozen ETF universe with synthetic prices (q12, C5)."""

import subprocess
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.events import CashDividend, InstrumentEvents
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Universe
from quantlab.research.definition import (
    TimeSeriesMomentumParameters,
    VolatilityTargetedMomentumParameters,
)
from quantlab.research.trials import registered_trials, trials_on_same_data
from quantlab.validation.holdout import parse_holdout_config

_REPO = Path(__file__).parents[1]
_CASH_RATE = 0.0001  # a day
# Daily volatility by asset class: equity and real estate swing most, bonds least.
_VOLATILITY = {
    "equity": 0.012,
    "real_estate": 0.015,
    "commodity": 0.011,
    "bond": 0.005,
    "currency": 0.004,
}
_DEFINITION = """hypothesis: {hypothesis}
training_start: 2009-01-01
training_end: 2010-12-31
start: 2011-01-01
end: 2011-06-30
parameters:
{strategy}  universe: multiasset-etf
  cost_model: {{name: realistic, fee_bps: 3, k: 0.05, vol_window: 21}}
success_criterion:
  description: test
  min_sharpe: 0.0
  max_p_value: 0.1
"""
_DEFINITIONS = {
    "etf_mom_v1": "  strategy: time_series_momentum\n  lookback_days: 252\n",
    "etf_vt_v1": (
        "  strategy: time_series_momentum_vol_target\n  lookback_days: 252\n"
        "  target_volatility: 0.1\n  max_scale: 1.0\n"
        "  volatility: {estimator: ewma, center_of_mass_days: 60, window_days: 252}\n"
    ),
}


def _sessions() -> list[date]:
    """Weekdays without New Year's Day and Christmas, from 2006 (before BIL listed)."""
    day, days = date(2006, 1, 2), []
    while day <= date(2011, 12, 31):
        if day.weekday() < 5 and (day.month, day.day) not in {(1, 1), (12, 25)}:
            days.append(day)
        day += timedelta(days=1)
    return days


class _Etfs:
    """Tiingo test double: each ETF trends up and down in turns with its class's
    volatility; BIL accrues interest and pays it out on each month's first session."""

    _CASH_START = date(2007, 5, 30)

    def __init__(self) -> None:
        universe = Universe.load("multiasset-etf")
        self.sessions = _sessions()
        rng = np.random.default_rng(12)
        n = len(self.sessions)
        self.closes: dict[str, np.ndarray] = {}
        for instrument in universe.instruments:
            drift = np.repeat(rng.choice([-0.0006, 0.0008], size=n // 120 + 1), 120)[:n]
            noise = _VOLATILITY[instrument.asset_class] * rng.normal(0.0, 1.0, n)
            self.closes[instrument.id] = 100.0 * np.cumprod(1.0 + drift + noise)
        cash_days = [day for day in self.sessions if day >= self._CASH_START]
        closes, self.distributions, accrued = [], {}, 50.0
        for i, day in enumerate(cash_days):
            if i and day.month != cash_days[i - 1].month:
                self.distributions[day] = accrued * (1.0 + _CASH_RATE) - 50.0
                accrued = 50.0
            elif i:
                accrued *= 1.0 + _CASH_RATE
            closes.append(accrued)
        self.cash = dict(zip(cash_days, closes, strict=True))

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        series = (
            self.cash
            if instrument.id == "bil"
            else dict(zip(self.sessions, self.closes[instrument.id], strict=True))
        )
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=day,
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e8,
                source="test",
            )
            for day, close in series.items()
            if start <= day <= end
        ]

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        actions = [
            CashDividend(instrument_id="bil", ex_date=day, amount=amount)
            for day, amount in self.distributions.items()
            if instrument.id == "bil" and start <= day <= end
        ]
        return InstrumentEvents(actions=actions, delisting=None)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _committed(tmp_path: Path, monkeypatch) -> None:
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
    monkeypatch.setitem(cli._PROVIDERS, "tiingo", _Etfs)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)


def test_momentum_on_etfs_trades_returns_above_cash_from_the_first_session(
    tmp_path, monkeypatch
) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["run", "etf_mom_v1"])

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert "Returns:        above cash (BIL)" in result.output
    # 252 sessions of warm-up: a signal on the first session (2009-01-02), so a position
    # from the second, the first snapshot being the starting capital.
    assert "First position: 2009-01-05" in lines
    assert "spy 21-session volatility tercile vs its last 252 sessions" in result.output
    assert "Trials on this universe and training period: 2 (" in result.output
    classes = {line.split()[0] for line in lines if line.split()[:1]}
    assert {"equity", "bond", "commodity", "currency", "real_estate"} <= classes


def test_both_engines_trade_the_scaled_etf_positions_alike(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["compare-engines", "etf_vt_v1"])

    assert result.exit_code == 0, result.output
    assert "Returns:        above cash (BIL)" in result.output
    parity = next(line for line in result.output.splitlines() if line.startswith("Parity"))
    assert "numerical noise only" in parity


def test_the_etf_universe_freezes_the_story_s_basket() -> None:
    universe = Universe.load("multiasset-etf")

    assert (universe.source, universe.periods_per_year, universe.market_proxy) == (
        "tiingo",
        252,
        "spy",
    )
    assert universe.is_static
    assert universe.cash is not None and universe.cash.symbol == "BIL"
    assert {i.symbol: i.asset_class for i in universe.instruments} == {
        "SPY": "equity",
        "EFA": "equity",
        "EEM": "equity",
        "IEF": "bond",
        "TLT": "bond",
        "LQD": "bond",
        "GLD": "commodity",
        "DBC": "commodity",
        "UUP": "currency",
        "VNQ": "real_estate",
    }


def test_the_cross_asset_hypotheses_freeze_the_story_s_answers() -> None:
    definitions = _REPO / "config" / "holdout"
    plain = parse_holdout_config(definitions / "momentum_multiasset_v1.yaml")
    scaled = parse_holdout_config(definitions / "momentum_voltarget_multiasset_v1.yaml")

    assert isinstance(plain.parameters, TimeSeriesMomentumParameters)
    assert isinstance(scaled.parameters, VolatilityTargetedMomentumParameters)
    assert plain.parameters.lookback_days == scaled.parameters.lookback_days == 252
    assert (scaled.parameters.target_volatility, scaled.parameters.max_scale) == (0.10, 1.0)
    assert scaled.parameters.volatility.model_dump() == {
        "estimator": "ewma",
        "window_days": 252,
        "center_of_mass_days": 60.0,
    }
    for config in (plain, scaled):
        parameters = config.parameters
        assert parameters.universe == "multiasset-etf"
        assert parameters.cost_model.model_dump() == {
            "name": "realistic",
            "fee_bps": 3.0,
            "k": 0.05,
            "vol_window": 21,
        }
        assert (config.training_start, config.training_end) == (
            date(2008, 7, 1),
            date(2017, 12, 31),
        )
        assert (config.start, config.end) == (date(2018, 1, 1), date(2026, 8, 31))
        assert config.success_criterion.in_sample_validation == "walk_forward"
        assert (config.success_criterion.min_sharpe, config.success_criterion.max_p_value) == (
            0.0,
            0.1,
        )
        # The warm-up in sessions starts fetching after BIL listed (May 2007).
        assert parameters.fetch_start(config.training_start, Universe.load("multiasset-etf")) > (
            date(2007, 5, 30)
        )
    # Two trials on a new universe: none of the crypto hypotheses counts.
    trials = trials_on_same_data("momentum_multiasset_v1", registered_trials(definitions))
    assert {trial.hypothesis for trial in trials} == {
        "momentum_multiasset_v1",
        "momentum_voltarget_multiasset_v1",
    }
