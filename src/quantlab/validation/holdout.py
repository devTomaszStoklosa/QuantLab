import subprocess
from datetime import date
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, model_validator


class HoldoutNotFrozenError(Exception):
    pass


class CostModelParameters(BaseModel):
    name: Literal["realistic"]
    fee_bps: float
    k: float
    vol_window: int


class HoldoutParameters(BaseModel):
    strategy: Literal["time_series_momentum"]
    lookback_days: int
    universe: str
    cost_model: CostModelParameters


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
    parameters: HoldoutParameters
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


def holdout_verdict(criterion: SuccessCriterion, sharpe: float, p_value: float) -> HoldoutVerdict:
    if sharpe <= criterion.min_sharpe:
        return "rejected"
    if p_value >= criterion.max_p_value:
        return "inconclusive"
    return "passed"
