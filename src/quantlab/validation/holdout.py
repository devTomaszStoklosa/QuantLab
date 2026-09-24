import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, model_validator

from quantlab.research.definition import StudyParameters


class HoldoutNotFrozenError(Exception):
    pass


class HoldoutAlreadyOpenedError(Exception):
    pass


class SuccessCriterion(BaseModel):
    description: str
    min_sharpe: float  # holdout Sharpe must be strictly greater
    max_p_value: float  # permutation p-value must be strictly lower


class HoldoutConfig(BaseModel):
    hypothesis: str
    training_start: date
    training_end: date
    start: date
    end: date
    parameters: StudyParameters  # the hypothesis definition, not only the holdout's
    success_criterion: SuccessCriterion

    @model_validator(mode="after")
    def _holdout_after_training(self) -> Self:
        if self.start <= self.training_end:
            raise ValueError(
                f"Holdout start {self.start} overlaps training (ends {self.training_end})"
            )
        if self.end < self.start:
            raise ValueError(f"Holdout end {self.end} is before its start {self.start}")
        return self


class FrozenHoldout(BaseModel):
    config: HoldoutConfig
    frozen_at_commit: str


HoldoutVerdict = Literal["passed", "inconclusive", "rejected"]


class HoldoutRecord(BaseModel):
    """Result of the one-time holdout opening, committed next to the frozen file."""

    hypothesis: str
    frozen_at_commit: str
    opened_at: datetime
    opened_at_commit: str
    start: date
    end: date
    cost_model_name: str
    cagr: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    p_value: float
    permutation: dict
    criterion: str
    verdict: HoldoutVerdict


def write_holdout_record(path: Path, record: HoldoutRecord) -> None:
    # Exclusive create: an existing record is never overwritten.
    with path.open("x", encoding="utf-8") as file:
        file.write(record.model_dump_json(indent=2) + "\n")


def read_holdout_record(path: Path) -> HoldoutRecord:
    return HoldoutRecord.model_validate_json(path.read_text(encoding="utf-8"))


def parse_holdout_config(path: Path) -> HoldoutConfig:
    return HoldoutConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _git(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=path.parent, capture_output=True, text=True, check=False
    )


def load_frozen_holdout(path: Path) -> FrozenHoldout:
    """The only sanctioned way to get holdout parameters (REQ-041).

    Refuses unless the file exists, is committed, and has no uncommitted
    changes; a missing file is a blocking error, not a silent skip.
    """
    path = path.resolve()
    if not path.exists():
        raise HoldoutNotFrozenError(f"No frozen holdout file at {path}")
    if _git(path, "status", "--porcelain", "--", path.name).stdout.strip():
        raise HoldoutNotFrozenError(f"{path.name} has uncommitted changes; commit it first")
    frozen_at_commit = _git(path, "log", "-1", "--format=%H", "--", path.name).stdout.strip()
    if not frozen_at_commit:
        raise HoldoutNotFrozenError(f"{path.name} has never been committed")
    return FrozenHoldout(config=parse_holdout_config(path), frozen_at_commit=frozen_at_commit)


def holdout_passed(verdict: HoldoutVerdict) -> bool | None:
    """The verdict in ValidationResult.passed terms: None is inconclusive."""
    return {"passed": True, "rejected": False, "inconclusive": None}[verdict]


def holdout_verdict(criterion: SuccessCriterion, sharpe: float, p_value: float) -> HoldoutVerdict:
    if sharpe <= criterion.min_sharpe:
        return "rejected"
    if p_value >= criterion.max_p_value:
        return "inconclusive"
    return "passed"
