"""The synthetic results store in presentation/fixtures/results (REQ-761).

The .NET API's tests and the UI's demo mode read it, so it is produced by the
full pipeline - `quantlab open-holdout`, `run` and `registry` on synthetic bars -
never written by hand: the .NET tests then check the real contract, not their
own assumptions. Its hypotheses are `demo_*` and its data source `synthetic`,
so it cannot pass for a research result. After changing what the store holds:

    QUANTLAB_UPDATE_FIXTURES=1 uv run pytest tests/test_results_fixture.py
"""

import math
import os
import shutil
import subprocess
import uuid
from datetime import UTC, date, datetime, timedelta
from itertools import count
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument

FIXTURE = Path(__file__).parents[1] / "presentation" / "fixtures" / "results"

_ORIGIN = date(2019, 1, 1)
_LAST = date(2024, 12, 31)
_CLOCK = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
_GIT_ENV = {
    "GIT_AUTHOR_NAME": "QuantLab fixtures",
    "GIT_AUTHOR_EMAIL": "fixtures@quantlab.invalid",
    "GIT_COMMITTER_NAME": "QuantLab fixtures",
    "GIT_COMMITTER_EMAIL": "fixtures@quantlab.invalid",
}

_DEFINITION = """hypothesis: {hypothesis}

training_start: 2020-01-01
training_end: 2022-12-31
start: 2023-01-01
end: 2023-06-30

parameters:
{strategy}  universe: mvp-crypto
  cost_model:
    name: realistic
    fee_bps: 10
    k: 0.05
    vol_window: 30

success_criterion:
  description: >-
    Synthetic demo. Holdout net Sharpe under the realistic cost model > 0 and
    permutation-test p-value < 0.1.
  min_sharpe: 0.0
  max_p_value: 0.1
"""

# Registered in this order; demo_reversal is never run.
_HYPOTHESES = {
    "demo_momentum": "  strategy: time_series_momentum\n  lookback_days: 90\n",
    "demo_reversal": "  strategy: short_term_reversal\n  formation_days: 7\n",
    "demo_pairs": (
        "  strategy: pairs_spread\n  dependent: eth-usdt\n  explanatory: btc-usdt\n"
        "  formation_days: 120\n  entry_z: 2.0\n  exit_z: 0.0\n  max_coint_p_value: 0.05\n"
    ),
}


class _SyntheticProvider(WithoutEvents):
    """One fixed price path per instrument from 2019 to 2024, whatever range is asked:
    BTC a random walk, ETH cointegrated with it (log-linear plus a mean-reverting spread)."""

    def __init__(self) -> None:
        rng = np.random.default_rng(20260924)
        days = (_LAST - _ORIGIN).days + 1
        log_btc = np.log(8_000.0) + np.cumsum(rng.normal(0.0008, 0.035, days))
        spread = np.zeros(days)
        shocks = rng.normal(0.0, 0.03, days)
        for i in range(1, days):
            spread[i] = 0.95 * spread[i - 1] + shocks[i]
        log_eth = np.log(150.0) + 1.1 * (log_btc - log_btc[0]) + spread
        self._closes = {"btc-usdt": np.exp(log_btc), "eth-usdt": np.exp(log_eth)}

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        closes = self._closes[instrument.id]
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_ORIGIN + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1_000_000.0,
                adj_close=None,
                source="synthetic",
            )
            for i, close in enumerate(closes)
            if start <= _ORIGIN + timedelta(days=i) <= end
        ]


class _FixedClock(datetime):
    @classmethod
    def now(cls, tz=None) -> datetime:
        return _CLOCK


def _commit(repo: Path, message: str, when: datetime, *paths: str) -> None:
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S+0000")
    env = os.environ | _GIT_ENV | {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    for args in (["add", *paths], ["commit", "-q", "-m", message]):
        subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def generate(directory: Path, monkeypatch) -> Path:
    """Write the synthetic store to `directory/results` and return its path."""
    repo, store = directory / "definitions", directory / "results"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
    for day, (hypothesis, strategy) in enumerate(_HYPOTHESES.items()):
        (repo / f"{hypothesis}.yaml").write_text(
            _DEFINITION.format(hypothesis=hypothesis, strategy=strategy), encoding="utf-8"
        )
        _commit(
            repo,
            f"freeze {hypothesis}",
            datetime(2026, 9, 1 + day, 9, 0, tzinfo=UTC),
            f"{hypothesis}.yaml",
        )
    provider = _SyntheticProvider()
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", store)
    monkeypatch.setattr(cli, "BinanceProvider", lambda: provider)
    monkeypatch.setattr(cli, "_PERMUTATIONS", 500)
    monkeypatch.setattr(cli, "_current_git_sha", lambda: "5e7f1c0de" + "0" * 31)
    monkeypatch.setattr(cli, "datetime", _FixedClock)
    ids = count(1)
    monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=next(ids)))  # run ids
    runner = CliRunner()
    for command in (
        ["open-holdout", "demo_momentum"],
        ["run", "demo_momentum", "--contrast", "demo_pairs"],
        ["run", "demo_pairs"],
        ["registry"],
    ):
        result = runner.invoke(cli.app, command)
        assert result.exit_code == 0, result.output
    return store


def _same(left: object, right: object) -> bool:
    """Equal, with floats compared to a relative 1e-9: the same code on another
    platform may differ in the last bits of a sum."""
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(map(_same, left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    return left == right


def _files(store: Path) -> list[str]:
    return sorted(path.relative_to(store).as_posix() for path in store.rglob("*.parquet"))


def test_the_committed_synthetic_store_is_what_the_pipeline_writes(tmp_path, monkeypatch) -> None:
    generated = generate(tmp_path, monkeypatch)
    if os.environ.get("QUANTLAB_UPDATE_FIXTURES"):
        shutil.rmtree(FIXTURE, ignore_errors=True)
        shutil.copytree(generated, FIXTURE)

    assert _files(FIXTURE) == _files(generated), (
        "Synthetic store is stale; regenerate it (see this module's docstring)"
    )
    for name in _files(generated):
        committed, fresh = pq.read_table(FIXTURE / name), pq.read_table(generated / name)
        assert committed.schema.remove_metadata() == fresh.schema.remove_metadata(), name
        assert _same(committed.to_pylist(), fresh.to_pylist()), (
            f"{name} differs from what the pipeline writes; regenerate the synthetic store"
        )


def test_the_synthetic_store_covers_each_registry_state() -> None:
    registry = pq.read_table(FIXTURE / "hypotheses.parquet").to_pylist()

    assert {row["hypothesis"]: (row["has_run"], row["holdout_verdict"]) for row in registry} == {
        "demo_momentum": (True, registry[0]["holdout_verdict"]),
        "demo_reversal": (False, None),
        "demo_pairs": (True, None),
    }
    assert registry[0]["holdout_verdict"] is not None
    assert [row["status"] for row in registry][1:] == ["proposed", "testing"]
    for hypothesis in ("demo_momentum", "demo_pairs"):
        [run] = pq.read_table(FIXTURE / hypothesis / "run.parquet").to_pylist()
        assert run["data_source"] == "synthetic"
