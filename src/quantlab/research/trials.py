import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from quantlab.validation.holdout import HoldoutConfig


class TrialRegistryError(Exception):
    pass


class Trial(BaseModel):
    """A hypothesis whose definition was committed: from then on it could be run (REQ-610)."""

    hypothesis: str
    universe: str
    training_start: date
    training_end: date
    registered_at: datetime  # first commit adding its definition
    last_commit: str  # last commit in which its definition existed
    deleted: bool  # its definition is gone from the current commit


def _git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=directory, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise TrialRegistryError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def registered_trials(definitions_dir: Path) -> list[Trial]:
    """Every hypothesis ever committed to `definitions_dir` in the current commit's history.

    A definition deleted later still counts, so removing a failed trial's file
    does not lower the count; a file never committed is a draft, not a trial;
    uncommitted edits are ignored in favour of the last committed version
    (REQ-610, REQ-611). Trials are keyed by hypothesis id, so a renamed file is
    one trial, at its most recently committed version. Oldest first.
    """
    directory = definitions_dir.resolve()
    output = _git(
        directory,
        "log",
        "--relative",
        "--no-renames",
        "--name-status",
        "--format=@%H %ct",
        "HEAD",
        "--",
        ".",
    )
    # git log lists commits newest first: a file's first entry is its latest
    # change, its first "A" or "M" entry its latest version, and its last "A"
    # entry the commit that first added it.
    latest_status: dict[str, str] = {}
    version: dict[str, tuple[int, str]] = {}  # name -> (commit rank, sha)
    first_added: dict[str, datetime] = {}
    rank, sha, committed_at = -1, "", datetime.min.replace(tzinfo=UTC)
    for line in output.splitlines():
        if line.startswith("@"):
            sha, timestamp = line[1:].split()
            committed_at = datetime.fromtimestamp(int(timestamp), tz=UTC)
            rank += 1
        elif line:
            status, name = line.split("\t", 1)
            if not name.endswith(".yaml"):
                continue
            latest_status.setdefault(name, status)
            if status in ("A", "M"):
                version.setdefault(name, (rank, sha))
            if status == "A":
                first_added[name] = committed_at

    chosen: dict[str, tuple[int, Trial]] = {}
    for name in sorted(first_added):
        version_rank, version_sha = version[name]
        try:
            config = HoldoutConfig.model_validate(
                yaml.safe_load(_git(directory, "show", f"{version_sha}:./{name}"))
            )
        except (yaml.YAMLError, ValidationError) as error:
            raise TrialRegistryError(
                f"{name} at {version_sha[:7]} is not a valid definition"
            ) from error
        trial = Trial(
            hypothesis=config.hypothesis,
            universe=config.parameters.universe,
            training_start=config.training_start,
            training_end=config.training_end,
            registered_at=first_added[name],
            last_commit=version_sha,
            deleted=latest_status[name] == "D",
        )
        earlier = chosen.get(trial.hypothesis)
        if earlier is not None:
            # The same hypothesis under another file name: one trial, registered
            # when its first file was, defined by its most recently committed file.
            registered_at = min(trial.registered_at, earlier[1].registered_at)
            if earlier[0] <= version_rank:
                trial, version_rank = earlier[1], earlier[0]
            trial = trial.model_copy(update={"registered_at": registered_at})
        chosen[trial.hypothesis] = (version_rank, trial)
    return sorted(
        (trial for _, trial in chosen.values()),
        key=lambda trial: (trial.registered_at, trial.hypothesis),
    )


def trials_on_same_data(hypothesis: str, trials: list[Trial]) -> list[Trial]:
    """Trials with the hypothesis's universe and an overlapping training period,
    itself included (REQ-612)."""
    target = next((trial for trial in trials if trial.hypothesis == hypothesis), None)
    if target is None:
        raise TrialRegistryError(f"{hypothesis} has no committed definition")
    return [
        trial
        for trial in trials
        if trial.universe == target.universe
        and trial.training_start <= target.training_end
        and target.training_start <= trial.training_end
    ]
