"""Hypothesis definitions: which strategy, with which parameters, on what, at what cost.

The committed frozen file (config/holdout/<id>.yaml) is the single definition
of a hypothesis (q3 03-design, Option A), so every run reads its parameters
from there. Each strategy's parameters are their own model and build their
own strategy: the runner never branches on the strategy type (REQ-301).
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

from quantlab.costs.realistic import RealisticCostModel
from quantlab.strategy.base import Strategy
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


# One variant per strategy; M2 turns this into a union keyed on `strategy`.
StudyParameters = TimeSeriesMomentumParameters
