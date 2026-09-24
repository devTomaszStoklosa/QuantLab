from typing import Literal, Protocol

from pydantic import BaseModel

from quantlab.backtest.run import BacktestRun

# The significance tests a success criterion can name (q5, REQ-563): the day
# shuffle of q1 asks about timing, random portfolios about selection.
SignificanceTest = Literal["day_shuffle", "random_portfolio"]


class ValidationResult(BaseModel):
    method: Literal["walk_forward", "permutation", "holdout"]
    passed: bool | None  # None = inconclusive
    detail: dict


class Validator(Protocol):
    def validate(self, run: BacktestRun) -> ValidationResult: ...
