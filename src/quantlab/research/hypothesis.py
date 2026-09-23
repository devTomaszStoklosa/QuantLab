import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Status = Literal["proposed", "testing", "confirmed", "rejected", "inconclusive"]

_ALLOWED_TRANSITIONS: dict[Status, set[Status]] = {
    "proposed": {"testing"},
    "testing": {"confirmed", "rejected", "inconclusive"},
    "confirmed": set(),
    "rejected": set(),
    "inconclusive": set(),
}

REGISTRY_PATH = Path("data/hypotheses.json")


class InvalidStatusTransitionError(Exception):
    def __init__(self, from_status: Status, to_status: Status) -> None:
        super().__init__(f"Cannot transition hypothesis from '{from_status}' to '{to_status}'")
        self.from_status = from_status
        self.to_status = to_status


class HypothesisNotValidatedError(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Cannot mark hypothesis 'confirmed' without both a passed walk-forward "
            "validation and a passed holdout evaluation"
        )


class HypothesisNotFoundError(Exception):
    def __init__(self, hypothesis_id: str) -> None:
        super().__init__(f"Unknown hypothesis '{hypothesis_id}'")


class DuplicateHypothesisError(Exception):
    def __init__(self, hypothesis_id: str) -> None:
        super().__init__(f"Hypothesis '{hypothesis_id}' already registered")


class Hypothesis(BaseModel):
    id: str
    title: str
    statement: str
    status: Status = "proposed"
    created_at: date

    def transition_to(
        self,
        new_status: Status,
        *,
        walk_forward_passed: bool = False,
        holdout_passed: bool = False,
    ) -> "Hypothesis":
        """Apply a status transition, enforcing REQ-002 (allowed transitions) and
        REQ-090 (confirmed requires both walk-forward and holdout evidence).
        `walk_forward_passed`/`holdout_passed` are booleans today; once S9-S11 add
        real Validator/ValidationResult classes, callers pass their .passed field
        instead of asserting it manually — this signature does not need to change.
        """
        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise InvalidStatusTransitionError(self.status, new_status)
        if new_status == "confirmed" and not (walk_forward_passed and holdout_passed):
            raise HypothesisNotValidatedError()
        return self.model_copy(update={"status": new_status})


def _load_all() -> dict[str, Hypothesis]:
    if not REGISTRY_PATH.exists():
        return {}
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {item["id"]: Hypothesis(**item) for item in raw}


def _save_all(hypotheses: dict[str, Hypothesis]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [hypothesis.model_dump(mode="json") for hypothesis in hypotheses.values()]
    REGISTRY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def register(hypothesis_id: str, title: str, statement: str) -> Hypothesis:
    hypotheses = _load_all()
    if hypothesis_id in hypotheses:
        raise DuplicateHypothesisError(hypothesis_id)
    hypothesis = Hypothesis(
        id=hypothesis_id, title=title, statement=statement, created_at=datetime.now(tz=UTC).date()
    )
    hypotheses[hypothesis_id] = hypothesis
    _save_all(hypotheses)
    return hypothesis


def get(hypothesis_id: str) -> Hypothesis:
    hypotheses = _load_all()
    if hypothesis_id not in hypotheses:
        raise HypothesisNotFoundError(hypothesis_id)
    return hypotheses[hypothesis_id]


def update_status(
    hypothesis_id: str,
    new_status: Status,
    *,
    walk_forward_passed: bool = False,
    holdout_passed: bool = False,
) -> Hypothesis:
    hypotheses = _load_all()
    if hypothesis_id not in hypotheses:
        raise HypothesisNotFoundError(hypothesis_id)
    updated = hypotheses[hypothesis_id].transition_to(
        new_status, walk_forward_passed=walk_forward_passed, holdout_passed=holdout_passed
    )
    hypotheses[hypothesis_id] = updated
    _save_all(hypotheses)
    return updated
