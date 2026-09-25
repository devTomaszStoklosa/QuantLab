from pathlib import Path

from quantlab.reporting.results_store import SCHEMA_VERSION
from quantlab.research.plan import (
    HypothesisState,
    RepositoryState,
    Step,
    StoredRun,
    build_plan,
    logged_hypotheses,
)

_CRYPTO = ["mom_v1", "rev_v1", "port_v1"]


def _hypothesis(name: str, **changes) -> HypothesisState:
    fields = {
        "hypothesis": name,
        "universe": "mvp-crypto",
        "source": "binance",
        "universe_path": "src/quantlab/config/universes/mvp-crypto.yaml",
        "universe_committed": True,
        "load_error": None,
        "trials": _CRYPTO,
        "stored": StoredRun(schema_version=SCHEMA_VERSION, trials=_CRYPTO),
        "record_path": f"config/holdout/{name}.opened.json",
        "record": False,
        "record_committed": False,
        "unopened_prerequisites": [],
    } | changes
    return HypothesisState(**fields)


def _plan(*hypotheses: HypothesisState, logged: set[str] = frozenset(), dotnet: bool = True):
    steps = build_plan(
        RepositoryState(hypotheses=list(hypotheses), logged=set(logged), dotnet=dotnet)
    )
    return {step.key: step for step in steps}, [step.key for step in steps]


def test_the_plan_keeps_the_order_checks_universes_runs_holdouts_commits_logs() -> None:
    _, keys = _plan(*(_hypothesis(name, stored=None) for name in _CRYPTO))

    assert keys == [
        "check:python",
        "check:dotnet",
        "check:binance",
        *(f"train:{name}" for name in _CRYPTO),
        *(f"holdout:{name}" for name in _CRYPTO),
        *(f"commit:{name}" for name in _CRYPTO),
        *(f"log:{name}" for name in _CRYPTO),
    ]


def test_a_stored_run_is_done_only_when_current() -> None:
    steps, _ = _plan(
        _hypothesis("mom_v1"),
        _hypothesis("rev_v1", stored=StoredRun(schema_version=2, trials=None)),
        _hypothesis("port_v1", stored=StoredRun(schema_version=SCHEMA_VERSION, trials=_CRYPTO[:2])),
    )

    assert steps["train:mom_v1"].state == "done"
    assert (steps["train:rev_v1"].state, steps["train:rev_v1"].reason) == (
        "pending",
        f"stored with schema v2, the store is v{SCHEMA_VERSION}",
    )
    assert steps["train:port_v1"].reason == "new trials on its data: port_v1"
    assert steps["train:port_v1"].command == [
        "quantlab",
        "run",
        "port_v1",
        "--tear-sheet",
        "reports/port_v1.html",
    ]


def test_no_source_is_checked_when_no_pending_run_reads_it() -> None:
    steps, keys = _plan(_hypothesis("mom_v1"), dotnet=False)

    assert "check:binance" not in keys
    assert (steps["check:dotnet"].state, steps["check:dotnet"].reason) == (
        "blocked",
        "dotnet is not on the path; the API is not checked",
    )


def test_a_holdout_waits_for_its_training_run_and_a_portfolio_for_its_components() -> None:
    steps, _ = _plan(
        _hypothesis("mom_v1", record=True, record_committed=True),
        _hypothesis("rev_v1", stored=None),
        _hypothesis("port_v1", unopened_prerequisites=["rev_v1"]),
    )

    assert steps["holdout:mom_v1"].state == "done"
    assert (steps["holdout:rev_v1"].state, steps["holdout:rev_v1"].reason) == (
        "blocked",
        "waits for train:rev_v1",
    )
    assert steps["holdout:port_v1"].reason == (
        "its holdout overlaps the unopened holdouts of rev_v1"
    )
    ready, _ = _plan(_hypothesis("port_v1"))
    assert (ready["holdout:port_v1"].state, ready["holdout:port_v1"].kind) == ("pending", "manual")
    assert ready["holdout:port_v1"].reason == "once only, after reviewing the training results"


def test_an_opening_record_is_committed_then_logged() -> None:
    steps, _ = _plan(
        _hypothesis("mom_v1", record=True, record_committed=True),
        _hypothesis("rev_v1", record=True),
        _hypothesis("port_v1"),
        logged={"mom_v1"},
    )

    assert [steps[f"commit:{name}"].state for name in _CRYPTO] == ["done", "pending", "blocked"]
    assert steps["commit:rev_v1"].command == ["git", "add", "config/holdout/rev_v1.opened.json"]
    assert [steps[f"log:{name}"].state for name in _CRYPTO] == ["done", "pending", "blocked"]
    assert all(steps[f"log:{name}"].kind == "manual" for name in _CRYPTO)


def _equities(**changes) -> HypothesisState:
    fields = {
        "universe": "sp500",
        "source": None,
        "universe_path": "src/quantlab/config/universes/sp500.yaml",
        "universe_committed": False,
        "trials": ["xs_v1"],
        "stored": None,
    } | changes
    return _hypothesis("xs_v1", **fields)


def test_a_universe_is_built_then_reviewed_before_its_run() -> None:
    missing, keys = _plan(_equities())
    built, _ = _plan(_equities(source="tiingo"))
    committed, committed_keys = _plan(_equities(source="tiingo", universe_committed=True))

    assert keys.index("universe:sp500") < keys.index("review:sp500") < keys.index("train:xs_v1")
    assert (missing["universe:sp500"].state, missing["universe:sp500"].kind) == ("pending", "auto")
    assert missing["review:sp500"].state == "blocked"
    assert missing["train:xs_v1"].state == "blocked"
    assert (built["universe:sp500"].state, built["review:sp500"].state) == ("done", "pending")
    assert built["review:sp500"].kind == "manual"
    assert built["train:xs_v1"].reason == "universe sp500 is built but not reviewed and committed"
    assert committed["train:xs_v1"].state == "pending"
    assert committed["check:tiingo"].command == ["quantlab", "check-source", "tiingo"]
    assert "check:binance" not in committed_keys


def test_a_definition_that_does_not_load_blocks_its_run() -> None:
    steps, _ = _plan(
        _hypothesis("port_v1", stored=None, load_error="rev_v1.yaml has uncommitted changes")
    )

    assert (steps["train:port_v1"].state, steps["train:port_v1"].reason) == (
        "blocked",
        "rev_v1.yaml has uncommitted changes",
    )


def test_manual_steps_carry_the_manual_kind() -> None:
    steps, _ = _plan(*(_hypothesis(name) for name in _CRYPTO))

    kinds = {key.split(":")[0]: step.kind for key, step in steps.items()}
    assert kinds == {
        "check": "check",
        "train": "auto",
        "holdout": "manual",
        "commit": "manual",
        "log": "manual",
    }
    assert all(isinstance(step, Step) for step in steps.values())


def test_the_research_log_is_read_by_its_entry_headings(tmp_path: Path) -> None:
    log = tmp_path / "RESEARCH_LOG.md"
    log.write_text(
        "# Dziennik\n\n## <data> — <nazwa hipotezy>\n\n## Wpisy\n\n"
        "## 2026-09-24 — momentum_v1: time-series momentum\n\n"
        "## 2026-10-02 — pairs_v1 na ETH/BTC\n",
        encoding="utf-8",
    )

    assert logged_hypotheses(log) == {"momentum_v1", "pairs_v1"}
    assert logged_hypotheses(tmp_path / "missing.md") == set()
