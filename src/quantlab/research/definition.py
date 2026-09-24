"""Hypothesis definitions: which strategy, with which parameters, on what, at what cost.

The committed frozen file (config/holdout/<id>.yaml) is the single definition
of a hypothesis (q3 03-design, Option A), so every run reads its parameters
from there. Each strategy's parameters are their own model and build their
own strategy: the runner never branches on the strategy type (REQ-301).
"""

from abc import ABC, abstractmethod
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from quantlab.backtest.sizing import EqualWeightBySign, PairWeights, Sizer
from quantlab.costs.realistic import RealisticCostModel
from quantlab.strategy.base import Strategy
from quantlab.strategy.pairs_spread import PairsSpreadReversion
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum


class CostModelParameters(BaseModel):
    """The realistic cost model; the naive one in the comparison uses the same fee.

    momentum_v1 froze fee_bps 10 (Binance spot default fee for regular users,
    0.1%) and k 0.05: trading a few minutes after the close moves the price by
    about sigma_daily * sqrt(minutes / 1440), 0.05-0.06 sigma for ~5 minutes.
    """

    name: Literal["realistic"]
    fee_bps: float
    k: float
    vol_window: int

    def build(self) -> RealisticCostModel:
        return RealisticCostModel(fee_bps=self.fee_bps, k=self.k, vol_window=self.vol_window)


class StudyParametersBase(BaseModel, ABC):
    """What every hypothesis defines besides its strategy's own parameters."""

    strategy: str
    universe: str
    cost_model: CostModelParameters

    @property
    @abstractmethod
    def warm_up_days(self) -> int:
        """Days of history needed before a window starts for a signal on its first day."""

    @abstractmethod
    def strategy_params(self) -> dict:
        """The strategy's own parameters, as recorded on the BacktestRun."""

    @abstractmethod
    def build_strategy(self) -> Strategy: ...

    def build_sizer(self) -> Sizer:
        """How the engines weight this strategy's signals: equally by sign by default."""
        return EqualWeightBySign()


class TimeSeriesMomentumParameters(StudyParametersBase):
    strategy: Literal["time_series_momentum"]
    lookback_days: int = Field(ge=1)

    @property
    def warm_up_days(self) -> int:
        return self.lookback_days

    def strategy_params(self) -> dict:
        return {"lookback_days": self.lookback_days}

    def build_strategy(self) -> Strategy:
        return TimeSeriesMomentum(lookback_days=self.lookback_days)


class ShortTermReversalParameters(StudyParametersBase):
    strategy: Literal["short_term_reversal"]
    formation_days: int = Field(ge=1)

    @property
    def warm_up_days(self) -> int:
        return self.formation_days

    def strategy_params(self) -> dict:
        return {"formation_days": self.formation_days}

    def build_strategy(self) -> Strategy:
        return ShortTermReversal(formation_days=self.formation_days)


class PairsSpreadParameters(StudyParametersBase):
    """A pair's log spread: `dependent` regressed on `explanatory` (q4)."""

    strategy: Literal["pairs_spread"]
    dependent: str
    explanatory: str
    formation_days: int = Field(ge=30)
    entry_z: float = Field(gt=0)
    exit_z: float = Field(ge=0)
    max_coint_p_value: float | None = Field(gt=0, lt=1)  # required; null = no filter

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.dependent == self.explanatory:
            raise ValueError("A pair needs two different instruments")
        if self.exit_z >= self.entry_z:
            raise ValueError("exit_z must be below entry_z")
        return self

    @property
    def warm_up_days(self) -> int:
        return self.formation_days

    def strategy_params(self) -> dict:
        return {
            "dependent": self.dependent,
            "explanatory": self.explanatory,
            "formation_days": self.formation_days,
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "max_coint_p_value": self.max_coint_p_value,
        }

    def build_strategy(self) -> Strategy:
        return PairsSpreadReversion(
            dependent=self.dependent,
            explanatory=self.explanatory,
            formation_days=self.formation_days,
            entry_z=self.entry_z,
            exit_z=self.exit_z,
            max_coint_p_value=self.max_coint_p_value,
        )

    def build_sizer(self) -> Sizer:
        return PairWeights()


# A definition's `strategy` field picks the variant; a new strategy is a new
# variant here, never a branch in the runner.
StudyParameters = Annotated[
    TimeSeriesMomentumParameters | ShortTermReversalParameters | PairsSpreadParameters,
    Field(discriminator="strategy"),
]
