"""Runs and holdouts check their data first (q14): errors stop, warnings are reported."""

import subprocess
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument

_FIRST, _LAST = date(2019, 1, 1), date(2022, 12, 31)
_DEFINITION = """hypothesis: mom_q
training_start: 2020-01-01
training_end: 2021-06-30
start: 2021-07-01
end: 2021-12-31
parameters:
  strategy: time_series_momentum
  lookback_days: 30
  universe: mvp-crypto
  cost_model: {name: realistic, fee_bps: 10, k: 0.05, vol_window: 30}
success_criterion:
  description: test
  min_sharpe: 0.0
  max_p_value: 0.1
"""
_DUPLICATE = date(2020, 6, 10)  # in training
_ZERO = date(2021, 9, 15)  # in the holdout only
_STALE = date(2020, 9, 1)  # six equal closes from here, in training


class _Market(WithoutEvents):
    """BTC and ETH every day; `defects` plants a duplicate bar, a zero close or stale closes."""

    defects: frozenset[str] = frozenset()

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        rng = np.random.default_rng(1 if instrument.id == "btc-usdt" else 2)
        days = (_LAST - _FIRST).days + 1
        closes = 100.0 * np.cumprod(1.0 + rng.normal(0.0005, 0.02, days))
        if "stale" in self.defects:
            i = (_STALE - _FIRST).days
            closes[i : i + 6] = closes[i]
        bars = []
        for i, close in enumerate(closes):
            ts = _FIRST + timedelta(days=i)
            if not start <= ts <= end:
                continue
            bar = PriceBar(
                instrument_id=instrument.id,
                ts=ts,
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e9,
                source="test",
            )
            if ts == _ZERO and "zero" in self.defects and instrument.id == "eth-usdt":
                bar = replace(bar, open=0.0, high=0.0, low=0.0, close=0.0)
            bars.append(bar)
            if ts == _DUPLICATE and "duplicate" in self.defects and instrument.id == "btc-usdt":
                bars.append(bar)
        return bars


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _committed(tmp_path: Path, monkeypatch, *defects: str) -> Path:
    repo = tmp_path / "definitions"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "mom_q.yaml").write_text(_DEFINITION, encoding="utf-8", newline="\n")
    _git(repo, "add", "mom_q.yaml")
    _git(repo, "commit", "-q", "-m", "freeze mom_q")
    market = type("_Defective", (_Market,), {"defects": frozenset(defects)})
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", tmp_path / "results")
    monkeypatch.setitem(cli._PROVIDERS, "binance", market)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    return repo


def test_a_duplicate_date_stops_the_run_before_any_result(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch, "duplicate")

    result = CliRunner().invoke(cli.app, ["run", "mom_q"])

    assert result.exit_code == 1
    assert "1 error(s) that make any result on them meaningless; nothing was computed" in (
        result.output
    )
    assert f"duplicate dates: btc-usdt {_DUPLICATE} - 2 bars on {_DUPLICATE}" in result.output
    assert "uv run quantlab check-data mom_q" in result.output
    assert "CAGR" not in result.output
    assert not (tmp_path / "results" / "mom_q").exists()


def test_check_data_lists_every_finding_of_the_training_data(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch, "duplicate", "stale", "zero")

    result = CliRunner().invoke(cli.app, ["check-data", "mom_q"])

    assert result.exit_code == 1
    assert "1 error(s), 2 warning(s)" in result.output  # stale closes on both coins
    assert "duplicate dates: 1 (error)" in result.output
    assert f"stale closes: btc-usdt {_STALE}" in result.output
    # The zero close lies in the holdout, which the command never reads.
    assert "non-positive prices: 0" in result.output
    assert str(_ZERO) not in result.output


def test_clean_data_pass_the_check(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch)

    result = CliRunner().invoke(cli.app, ["check-data", "mom_q"])

    assert result.exit_code == 0, result.output
    assert "2 instruments" in result.output and "0 error(s), 0 warning(s)" in result.output


def test_warnings_are_reported_and_stored_and_the_run_goes_on(tmp_path, monkeypatch) -> None:
    _committed(tmp_path, monkeypatch, "stale")

    result = CliRunner().invoke(cli.app, ["run", "mom_q"])

    assert result.exit_code == 0, result.output
    assert "Data quality (training 2020-01-01 .. 2021-06-30):" in result.output
    assert "Data quality warnings to look at (2 of 2; all: uv run quantlab check-data mom_q):" in (
        result.output
    )
    assert f"  stale closes: btc-usdt {_STALE} - close" in result.output
    stored = pq.read_table(tmp_path / "results" / "mom_q" / "diagnostics.parquet").to_pylist()
    counts = {row["label"]: row["value"] for row in stored if row["title"] == "Data quality"}
    assert counts["stale closes"] == 2.0
    assert counts["duplicate dates"] == 0.0
    assert counts["instruments checked"] == 2.0


def test_a_holdout_with_an_error_in_its_data_is_not_opened(tmp_path, monkeypatch) -> None:
    repo = _committed(tmp_path, monkeypatch, "zero")

    result = CliRunner().invoke(cli.app, ["open-holdout", "mom_q"])

    assert result.exit_code == 1
    assert f"non-positive prices: eth-usdt {_ZERO}" in result.output
    assert "Sharpe" not in result.output
    assert not (repo / "mom_q.opened.json").exists()
