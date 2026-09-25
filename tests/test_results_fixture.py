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
from quantlab.core.data.events import Delisting, InstrumentEvents, Split
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe
from quantlab.research.hypothesis import concluded_status
from quantlab.validation.holdout import holdout_passed

FIXTURE = Path(__file__).parents[1] / "presentation" / "fixtures" / "results"

_ORIGIN = date(2019, 1, 1)
_LAST = date(2024, 12, 31)
_CLOCK = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
# The definitions' commit hashes end up in the store, so the temporary repo must
# not see the machine's git config: a signing key or hook there would change them.
_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
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

# Cross-sectional momentum on a synthetic point-in-time equity universe (q5).
_EQUITY_DEFINITION = """hypothesis: demo_xsmom

training_start: 2020-01-01
training_end: 2022-12-31
start: 2023-01-01
end: 2023-06-30

parameters:
  strategy: cross_sectional_momentum
  formation_months: 12
  skip_months: 1
  quantile: 0.2
  long_short: true
  min_price: 5.0
  missing_delisting_return: -0.3
  universe: demo-equities
  cost_model:
    name: realistic
    fee_bps: 5
    k: 0.05
    vol_window: 30

success_criterion:
  description: >-
    Synthetic demo. Holdout net Sharpe under the realistic cost model > 0 and
    random-portfolio test p-value < 0.1.
  min_sharpe: 0.0
  max_p_value: 0.1
  significance_test: random_portfolio
"""

# Time-series momentum choosing its lookback each year from a grid, with the CPCV
# of that choice as its frozen in-sample gate (q8). Same universe and training
# period as the crypto demos, so it is a trial on their data, with three configurations.
_SELECTION_DEFINITION = """hypothesis: demo_select

training_start: 2020-01-01
training_end: 2022-12-31
start: 2023-01-01
end: 2023-06-30

parameters:
  strategy: time_series_momentum_selected
  lookback_grid: [30, 90, 180]
  history_start: 2019-07-01
  min_history_days: 180
  universe: mvp-crypto
  cost_model:
    name: realistic
    fee_bps: 10
    k: 0.05
    vol_window: 30

success_criterion:
  description: >-
    Synthetic demo. Median Sharpe of the CPCV paths > 0 in training; holdout net
    Sharpe under the realistic cost model > 0 and permutation-test p-value < 0.1.
  min_sharpe: 0.0
  max_p_value: 0.1
  in_sample_validation: cpcv
  cpcv:
    groups: 10
    test_groups: 2
    purge_days: 1
    embargo_fraction: 0.01
"""

_STOCKS = [f"eq{i:02d}" for i in range(30)]
_INDEX = "eqidx"  # the market proxy: a benchmark without membership, never traded (REQ-501)
_SPLIT = date(2021, 3, 1)  # eq03, 4:1
_DELISTINGS = {  # instrument -> (delisting date, return; None: the definition's assumption)
    "eq28": (date(2021, 6, 15), -0.6),
    "eq29": (date(2022, 3, 10), None),
}
_EQUITIES = Universe(
    name="demo-equities",
    asof_date=_LAST,
    source="synthetic",
    periods_per_year=252,
    market_proxy=_INDEX,
    instruments=[
        Instrument(id=name, symbol=name.upper(), asset_class="equity", quote_asset="USD")
        for name in [*_STOCKS, _INDEX]
    ],
    memberships=[
        *(Membership(instrument_id=name, start=_ORIGIN, end=None) for name in _STOCKS[:24]),
        Membership(instrument_id="eq24", start=_ORIGIN, end=date(2021, 9, 30)),  # left the index
        *(  # joined the index
            Membership(instrument_id=name, start=date(2020, 7, 1), end=None)
            for name in _STOCKS[25:28]
        ),
        *(
            Membership(instrument_id=name, start=_ORIGIN, end=delisted)
            for name, (delisted, _) in _DELISTINGS.items()
        ),
    ],
)

# Registered in this order; demo_reversal is never run.
_HYPOTHESES = {
    "demo_momentum": "  strategy: time_series_momentum\n  lookback_days: 90\n",
    "demo_reversal": "  strategy: short_term_reversal\n  formation_days: 7\n",
    "demo_pairs": (
        "  strategy: pairs_spread\n  dependent: eth-usdt\n  explanatory: btc-usdt\n"
        "  formation_days: 120\n  entry_z: 2.0\n  exit_z: 0.0\n  max_coint_p_value: 0.05\n"
    ),
}


class _SyntheticProvider:
    """One fixed price path per instrument from 2019 to 2024, whatever range is asked:
    BTC a random walk, ETH cointegrated with it (log-linear plus a mean-reverting spread);
    stocks on business days, with a split and two delistings, and their average as the index."""

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
        drifts = rng.normal(0.0002, 0.0006, len(_STOCKS))
        for name, drift in zip(_STOCKS, drifts, strict=True):
            self._closes[name] = 40.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.018, days))
        self._closes[_INDEX] = np.mean([self._closes[name] for name in _STOCKS], axis=0)

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        closes = self._closes[instrument.id]
        equity = instrument.asset_class == "equity"
        last = (
            _DELISTINGS[instrument.id][0] - timedelta(days=1)
            if instrument.id in _DELISTINGS
            else end
        )
        bars = []
        for i, close in enumerate(closes):
            day = _ORIGIN + timedelta(days=i)
            if not start <= day <= min(end, last) or (equity and day.weekday() >= 5):
                continue
            quoted = float(close) / (4.0 if instrument.id == "eq03" and day >= _SPLIT else 1.0)
            bars.append(
                PriceBar(
                    instrument_id=instrument.id,
                    ts=day,
                    open=quoted,
                    high=quoted,
                    low=quoted,
                    close=quoted,
                    volume=1_000_000.0,
                    adj_close=None,
                    source="synthetic",
                )
            )
        return bars

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        actions = []
        if instrument.id == "eq03" and start <= _SPLIT <= end:
            actions.append(Split(instrument_id="eq03", ex_date=_SPLIT, ratio=4.0))
        delisting = None
        if instrument.id in _DELISTINGS and start <= _DELISTINGS[instrument.id][0] <= end:
            delisted, rate = _DELISTINGS[instrument.id]
            delisting = Delisting(instrument_id=instrument.id, date=delisted, delisting_return=rate)
        return InstrumentEvents(actions=actions, delisting=delisting)


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
    subprocess.run(
        ["git", "init", "-q"], cwd=repo, env=os.environ | _GIT_ENV, check=True, capture_output=True
    )
    for day, (hypothesis, strategy) in enumerate(_HYPOTHESES.items()):
        (repo / f"{hypothesis}.yaml").write_text(
            _DEFINITION.format(hypothesis=hypothesis, strategy=strategy),
            encoding="utf-8",
            newline="\n",  # the same blobs, so the same commit hashes, on Windows
        )
        _commit(
            repo,
            f"freeze {hypothesis}",
            datetime(2026, 9, 1 + day, 9, 0, tzinfo=UTC),
            f"{hypothesis}.yaml",
        )
    (repo / "demo_xsmom.yaml").write_text(_EQUITY_DEFINITION, encoding="utf-8", newline="\n")
    _commit(repo, "freeze demo_xsmom", datetime(2026, 9, 5, 9, 0, tzinfo=UTC), "demo_xsmom.yaml")
    (repo / "demo_select.yaml").write_text(_SELECTION_DEFINITION, encoding="utf-8", newline="\n")
    _commit(repo, "freeze demo_select", datetime(2026, 9, 6, 9, 0, tzinfo=UTC), "demo_select.yaml")
    provider = _SyntheticProvider()
    load = Universe.load
    monkeypatch.setattr(
        Universe,
        "load",
        classmethod(lambda cls, name: _EQUITIES if name == _EQUITIES.name else load(name)),
    )
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(cli, "_RESULTS_DIR", store)
    monkeypatch.setitem(cli._PROVIDERS, "binance", lambda: provider)
    monkeypatch.setitem(cli._PROVIDERS, "synthetic", lambda: provider)
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
        ["run", "demo_xsmom"],
        ["open-holdout", "demo_select"],
        ["run", "demo_select"],
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
        "demo_xsmom": (True, None),
        "demo_select": (True, registry[4]["holdout_verdict"]),
    }
    assert registry[0]["holdout_verdict"] is not None
    assert registry[4]["holdout_verdict"] is not None
    assert [row["status"] for row in registry][1:4] == ["proposed", "testing", "testing"]
    for hypothesis in ("demo_momentum", "demo_pairs", "demo_xsmom", "demo_select"):
        [run] = pq.read_table(FIXTURE / hypothesis / "run.parquet").to_pylist()
        assert run["data_source"] == "synthetic"
    assert {row["hypothesis"]: row["significance_test"] for row in registry} == {
        "demo_momentum": "day_shuffle",
        "demo_reversal": "day_shuffle",
        "demo_pairs": "day_shuffle",
        "demo_xsmom": "random_portfolio",
        "demo_select": "day_shuffle",
    }
    assert [row["in_sample_validation"] for row in registry] == ["walk_forward"] * 4 + ["cpcv"]


def test_the_equity_demo_is_a_point_in_time_cross_section() -> None:
    [run] = pq.read_table(FIXTURE / "demo_xsmom" / "run.parquet").to_pylist()
    trades = pq.read_table(FIXTURE / "demo_xsmom" / "trades.parquet").to_pylist()

    assert run["strategy"] == "cross_sectional_momentum"
    assert run["trials"] == ["demo_xsmom"]  # the only trial on this universe
    # Selection, not timing: random portfolios from the ranking find the edge (REQ-564).
    assert run["permutation_test"] == "random_portfolio"
    assert run["permutation_p_value"] < 0.1
    assert {trade["side"] for trade in trades} == {"long", "short"}
    assert _INDEX not in {trade["instrument_id"] for trade in trades}
    for trade in trades:
        membership = [m for m in _EQUITIES.memberships if m.instrument_id == trade["instrument_id"]]
        assert any(m.covers(trade["entry_ts"]) for m in membership), trade


def test_the_selection_demo_stores_its_grid_and_its_gate_decides() -> None:
    registry = {
        row["hypothesis"]: row for row in pq.read_table(FIXTURE / "hypotheses.parquet").to_pylist()
    }
    [run] = pq.read_table(FIXTURE / "demo_select" / "run.parquet").to_pylist()
    selection = pq.read_table(FIXTURE / "demo_select" / "selection.parquet").to_pylist()
    paths = pq.read_table(FIXTURE / "demo_select" / "cpcv_paths.parquet").to_pylist()

    assert (run["in_sample_validation"], run["cpcv_groups"], run["cpcv_paths"]) == ("cpcv", 10, 9)
    assert len(paths) == 9
    assert {row["year"] for row in selection} == {2020, 2021, 2022}
    assert sum(row["chosen"] for row in selection) == 3  # one value a year
    # Its three lookbacks count toward the trials of the other crypto demos (REQ-820).
    [momentum] = pq.read_table(FIXTURE / "demo_momentum" / "run.parquet").to_pylist()
    assert momentum["trials"][-1] == "demo_select"
    assert momentum["configurations"] == len(momentum["trials"]) + 2
    # The status follows the CPCV, not the walk-forward.
    verdict = holdout_passed(registry["demo_select"]["holdout_verdict"])
    assert registry["demo_select"]["status"] == concluded_status(run["in_sample_passed"], verdict)
