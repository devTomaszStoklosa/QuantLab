from typing import Literal, Protocol

from pydantic import BaseModel

from quantlab.backtest.vectorized.engine import BacktestRun


class ValidationResult(BaseModel):
    method: Literal["walk_forward", "permutation", "holdout"]
    passed: bool | None  # None = inconclusive
    detail: dict


class Validator(Protocol):
    def validate(self, run: BacktestRun) -> ValidationResult: ...
