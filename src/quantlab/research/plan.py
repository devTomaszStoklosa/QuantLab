"""What is left to do on a machine with the data, in the only order that keeps the
holdouts honest (q10, REQ-1001..1011).

The plan is a function of the repository and the results store: committed
definitions and their trials, opening records, stored runs, universe files, git
status and the research log. It changes nothing; `quantlab plan --run` executes
its checks and automatic steps, each as a plain command. Opening a holdout,
committing, reviewing a built universe and writing the research log are manual
steps: the researcher's, never the runner's.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import pyarrow.parquet as pq
from pydantic import BaseModel

from quantlab.core.universe import Universe
from quantlab.reporting.results_store import RUN_FILE, SCHEMA_VERSION
from quantlab.research.trials import Trial, registered_trials, trials_on_same_data
from quantlab.validation.holdout import HoldoutNotFrozenError, load_frozen_holdout

StepKind = Literal["check", "auto", "manual"]
StepState = Literal["done", "pending", "blocked"]

# Universes quantlab can build, and the command that builds each (q5, REQ-553).
UNIVERSE_BUILDERS: dict[str, list[str]] = {"sp500": ["quantlab", "build-universe"]}
# The data sources a pending run reads, checked before any of them (REQ-1010).
SOURCE_CHECKS = ("binance", "tiingo")
_LOG_ENTRY = re.compile(r"^## \d{4}-\d{2}-\d{2} — ([A-Za-z0-9_]+)")


class Step(BaseModel):
    """One line of the plan."""

    key: str
    title: str
    kind: StepKind
    state: StepState
    reason: str | None = None
    command: list[str] | None = None


@dataclass(frozen=True)
class StoredRun:
    schema_version: int
    trials: list[str] | None  # None in a schema that did not store them


@dataclass(frozen=True)
class HypothesisState:
    """What the repository says about one committed hypothesis."""

    hypothesis: str
    universe: str
    source: str | None  # the universe's data source; None while it is not available
    universe_path: str  # the universe file, relative to the repository
    universe_committed: bool
    load_error: str | None  # why its definition (or a component) does not load
    trials: list[str]  # today's trials on its data, registration order
    stored: StoredRun | None
    record_path: str
    record: bool
    record_committed: bool
    unopened_prerequisites: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepositoryState:
    hypotheses: list[HypothesisState]
    logged: set[str]  # hypotheses with a research-log entry
    dotnet: bool  # the .NET SDK is on the path


def _git_committed(path: Path) -> bool:
    """Tracked, and without changes in the work tree or the index (in the file's own repo)."""

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args, "--", path.name],
            cwd=path.parent,
            capture_output=True,
            text=True,
            check=False,
        )

    return (
        git("ls-files", "--error-unmatch").returncode == 0
        and not git("status", "--porcelain").stdout.strip()
    )


def _stored_run(store: Path, hypothesis: str) -> StoredRun | None:
    path = store / hypothesis / RUN_FILE
    if not path.exists():
        return None
    columns = pq.read_schema(path).names
    wanted = [name for name in ("schema_version", "trials") if name in columns]
    rows = pq.read_table(path, columns=wanted).to_pylist()
    if len(rows) != 1:
        return None
    return StoredRun(schema_version=rows[0]["schema_version"], trials=rows[0].get("trials"))


def logged_hypotheses(research_log: Path) -> set[str]:
    """Hypotheses with an entry heading `## <date> — <hypothesis>...` (REQ-1007)."""
    if not research_log.exists():
        return set()
    return {
        match.group(1)
        for line in research_log.read_text(encoding="utf-8").splitlines()
        if (match := _LOG_ENTRY.match(line))
    }


def read_state(
    repository: Path,
    definitions: Path,
    store: Path,
    universes: Path,
    research_log: Path,
    dotnet: bool,
) -> RepositoryState:
    """The state the plan is computed from; reads files and git, never the network."""
    trials = registered_trials(definitions)
    current = [trial for trial in trials if not trial.deleted]
    records = {
        trial.hypothesis: definitions / f"{trial.hypothesis}.opened.json" for trial in current
    }
    states = [
        _hypothesis_state(repository, definitions, store, universes, trial, trials, records)
        for trial in current
    ]
    return RepositoryState(hypotheses=states, logged=logged_hypotheses(research_log), dotnet=dotnet)


def _hypothesis_state(
    repository: Path,
    definitions: Path,
    store: Path,
    universes: Path,
    trial: Trial,
    trials: list[Trial],
    records: dict[str, Path],
) -> HypothesisState:
    universe_name = trial.universe
    universe_file = universes / f"{universe_name}.yaml"
    try:
        source = Universe.load(universe_name).source
    except ValueError:
        source = None
    load_error, unopened = None, []
    try:
        config = load_frozen_holdout(definitions / trial.path).config

        def component(hypothesis: str):
            return load_frozen_holdout(definitions / f"{hypothesis}.yaml").config

        parameters = config.parameters.resolve(component)
        unopened = [
            hypothesis
            for hypothesis in parameters.holdout_prerequisites(config.start, config.end)
            if not (definitions / f"{hypothesis}.opened.json").exists()
        ]
    except (HoldoutNotFrozenError, ValueError) as error:
        load_error = str(error)
    record = records[trial.hypothesis]
    return HypothesisState(
        hypothesis=trial.hypothesis,
        universe=universe_name,
        source=source,
        universe_path=_relative(repository, universe_file),
        universe_committed=universe_file.exists() and _git_committed(universe_file),
        load_error=load_error,
        trials=[t.hypothesis for t in trials_on_same_data(trial.hypothesis, trials)],
        stored=_stored_run(store, trial.hypothesis),
        record_path=_relative(repository, record),
        record=record.exists(),
        record_committed=record.exists() and _git_committed(record),
        unopened_prerequisites=unopened,
    )


def _relative(repository: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repository.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _stale(state: HypothesisState) -> str | None:
    """Why the stored run is not current, or None when it is (REQ-1003)."""
    stored = state.stored
    if stored is None:
        return "no run in the results store"
    if stored.schema_version != SCHEMA_VERSION:
        return f"stored with schema v{stored.schema_version}, the store is v{SCHEMA_VERSION}"
    if stored.trials != state.trials:
        added = [t for t in state.trials if t not in (stored.trials or [])]
        removed = [t for t in (stored.trials or []) if t not in state.trials]
        changes = [f"new trials on its data: {', '.join(added)}"] if added else []
        changes += [f"trials gone: {', '.join(removed)}"] if removed else []
        return "; ".join(changes) or "trials on its data reordered"
    return None


def _universe_steps(state: RepositoryState) -> list[Step]:
    steps = []
    for name in dict.fromkeys(h.universe for h in state.hypotheses if _stale(h) is not None):
        hypotheses = [h for h in state.hypotheses if h.universe == name]
        available = hypotheses[0].source is not None
        path = hypotheses[0].universe_path
        if name in UNIVERSE_BUILDERS:
            steps.append(
                Step(
                    key=f"universe:{name}",
                    title=f"Build the {name} universe",
                    kind="auto",
                    state="done" if available else "pending",
                    reason=None if available else f"{path} does not exist",
                    command=UNIVERSE_BUILDERS[name],
                )
            )
            committed = hypotheses[0].universe_committed
            steps.append(
                Step(
                    key=f"review:{name}",
                    title=f"Review the {name} build report, then commit the universe",
                    kind="manual",
                    state="done" if committed else ("pending" if available else "blocked"),
                    reason=None
                    if committed
                    else (
                        f"{path} is not committed; correct tickers only from the build report"
                        if available
                        else f"waits for universe:{name}"
                    ),
                    command=["git", "add", path] if available and not committed else None,
                )
            )
    return steps


def _ready_universe(h: HypothesisState) -> str | None:
    """Why the hypothesis's universe keeps its training run blocked, or None."""
    if h.source is None:
        return f"universe {h.universe} does not exist ({h.universe_path})"
    if h.universe in UNIVERSE_BUILDERS and not h.universe_committed:
        return f"universe {h.universe} is built but not reviewed and committed"
    return None


def build_plan(state: RepositoryState) -> list[Step]:
    """Every step left, in the order that must be kept (REQ-1001)."""
    hypotheses = state.hypotheses
    training: list[Step] = []
    for h in hypotheses:
        stale = _stale(h)
        blocker = h.load_error or _ready_universe(h)
        training.append(
            Step(
                key=f"train:{h.hypothesis}",
                title=f"Training run of {h.hypothesis}",
                kind="auto",
                state="done" if stale is None else ("blocked" if blocker else "pending"),
                reason=None if stale is None else (blocker or stale),
                command=[
                    "quantlab",
                    "run",
                    h.hypothesis,
                    "--tear-sheet",
                    f"reports/{h.hypothesis}.html",
                ],
            )
        )
    trained = {step.key.split(":", 1)[1] for step in training if step.state == "done"}
    needs = {
        h.source
        for h, step in zip(hypotheses, training, strict=True)
        if step.state == "pending" and h.source in SOURCE_CHECKS
    }

    checks = [
        Step(
            key="check:python",
            title="Native Python packages load and compute (DuckDB, statsmodels; no AVX2)",
            kind="check",
            state="pending",
            command=["pytest", "-q", "tests/test_environment.py"],
        ),
        Step(
            key="check:dotnet",
            title="DuckDB loads in the .NET API (no AVX2)",
            kind="check",
            state="pending" if state.dotnet else "blocked",
            reason=None if state.dotnet else "dotnet is not on the path; the API is not checked",
            command=[
                "dotnet",
                "test",
                "--solution",
                "presentation/QuantLab.Presentation.slnx",
                "--filter-class",
                "QuantLab.Api.Tests.EnvironmentTests",
            ],
        ),
        *(
            Step(
                key=f"check:{source}",
                title=f"{source} answers (a pending run reads it)",
                kind="check",
                state="pending",
                command=["quantlab", "check-source", source],
            )
            for source in SOURCE_CHECKS
            if source in needs
        ),
    ]

    holdouts, commits, logs = [], [], []
    for h in hypotheses:
        if h.record:
            holdout_state, holdout_reason = "done", None
        elif h.hypothesis not in trained:
            holdout_state, holdout_reason = "blocked", f"waits for train:{h.hypothesis}"
        elif h.unopened_prerequisites:
            holdout_state = "blocked"
            holdout_reason = (
                f"its holdout overlaps the unopened holdouts of "
                f"{', '.join(h.unopened_prerequisites)}"
            )
        else:
            holdout_state = "pending"
            holdout_reason = "once only, after reviewing the training results"
        holdouts.append(
            Step(
                key=f"holdout:{h.hypothesis}",
                title=f"Open the holdout of {h.hypothesis}",
                kind="manual",
                state=holdout_state,
                reason=holdout_reason,
                command=["quantlab", "open-holdout", h.hypothesis],
            )
        )
        commits.append(
            Step(
                key=f"commit:{h.hypothesis}",
                title=f"Commit the opening record of {h.hypothesis}",
                kind="manual",
                state="done" if h.record_committed else ("pending" if h.record else "blocked"),
                reason=None
                if h.record_committed
                else (
                    f"{h.record_path} is not committed"
                    if h.record
                    else f"waits for holdout:{h.hypothesis}"
                ),
                command=["git", "add", h.record_path],
            )
        )
        logged = h.hypothesis in state.logged
        logs.append(
            Step(
                key=f"log:{h.hypothesis}",
                title=f"Research-log entry for {h.hypothesis}",
                kind="manual",
                state="done" if logged else ("pending" if h.record else "blocked"),
                reason=None
                if logged
                else (
                    "docs/RESEARCH_LOG.md has no entry for it"
                    if h.record
                    else f"waits for holdout:{h.hypothesis}"
                ),
                # A draft from the stored numbers to start from (q13, REQ-1340).
                command=None
                if logged or not h.record
                else [
                    "quantlab",
                    "narrate",
                    h.hypothesis,
                    "--output",
                    f"reports/{h.hypothesis}-log.md",
                ],
            )
        )
    return [*checks, *_universe_steps(state), *training, *holdouts, *commits, *logs]
