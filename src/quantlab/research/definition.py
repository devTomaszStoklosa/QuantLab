"""Hypothesis definitions: which strategy, with which parameters, on what, at what cost.

The committed frozen file (config/holdout/<id>.yaml) is the single definition
of a hypothesis (q3 03-design, Option A), so every run reads its parameters
from there. Each strategy's parameters are their own model and build their
own strategy: the runner never branches on the strategy type (REQ-301).
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Annotated, Literal, Self

import numpy as np
from pydantic import BaseModel, Field, model_validator

from quantlab.backtest.rebalance import Daily, OnSignalChange, RebalancePolicy
from quantlab.backtest.sizing import EqualWeightBySign, PairWeights, Sizer
from quantlab.core.data.provider import PriceBar
from quantlab.costs.realistic import RealisticCostModel
from quantlab.strategy.base import Strategy
from quantlab.strategy.cointegration import engle_granger
from quantlab.strategy.cross_sectional_momentum import CrossSectionalMomentum
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


class TrainingDiagnostic(BaseModel):
    """A strategy-specific statistic of the training data, reported descriptively."""

    title: str
    values: dict[str, float | None]  # label -> value, in display order


class StudyParametersBase(BaseModel, ABC):
    """What every hypothesis defines besides its strategy's own parameters."""

    strategy: str
    universe: str
    cost_model: CostModelParameters
    # What holders got when a company was delisted and the source does not say
    # (q5, REQ-522): a frozen research assumption, e.g. -0.3 after Shumway (1997).
    # None - the default - makes a run with such a delisting refuse.
    missing_delisting_return: float | None = Field(default=None, ge=-1.0)

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

    def build_rebalance_policy(self) -> RebalancePolicy:
        """When the engines trade back to the targets: every period by default (REQ-532)."""
        return Daily()

    def training_diagnostics(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> list[TrainingDiagnostic]:
        """Statistics of the training data this strategy's reader needs; none by default."""
        return []


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

    def training_diagnostics(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> list[TrainingDiagnostic]:
        """Engle-Granger test and half-life over the whole training period (REQ-430).

        Descriptive: the strategy itself only ever tests trailing windows.
        """
        explanatory = {
            bar.ts: bar.close for bar in bars[self.explanatory] if start <= bar.ts <= end
        }
        common = sorted(
            (bar.ts, bar.close, explanatory[bar.ts])
            for bar in bars[self.dependent]
            if start <= bar.ts <= end and bar.ts in explanatory
        )
        result = engle_granger(np.log([y for _, y, _ in common]), np.log([x for _, _, x in common]))
        return [
            TrainingDiagnostic(
                title=f"Cointegration of {self.dependent} on {self.explanatory}",
                values={
                    "days": float(result.n_observations),
                    "hedge ratio": result.beta,
                    "Engle-Granger statistic": result.statistic,
                    "5% critical value": result.critical_values["5%"],
                    "p-value": result.p_value,
                    "half-life (days)": result.half_life,
                },
            )
        ]


class CrossSectionalMomentumParameters(StudyParametersBase):
    """Momentum ranked across a point-in-time equity universe (q5, REQ-540)."""

    strategy: Literal["cross_sectional_momentum"]
    formation_months: int = Field(ge=2)
    skip_months: int = Field(ge=0)
    quantile: float = Field(gt=0, le=0.5)
    long_short: bool
    min_price: float = Field(ge=0)
    # Required here: an equity universe has delistings, so the assumption is frozen upfront.
    missing_delisting_return: float = Field(ge=-1.0)

    @model_validator(mode="after")
    def _window(self) -> Self:
        if self.skip_months >= self.formation_months:
            raise ValueError("skip_months must be below formation_months")
        return self

    @property
    def warm_up_days(self) -> int:
        # Back to the start of month m-1-formation_months for the first day of the window.
        return (self.formation_months + 2) * 31

    def strategy_params(self) -> dict:
        return {
            "formation_months": self.formation_months,
            "skip_months": self.skip_months,
            "quantile": self.quantile,
            "long_short": self.long_short,
            "min_price": self.min_price,
        }

    def build_strategy(self) -> Strategy:
        return CrossSectionalMomentum(
            formation_months=self.formation_months,
            skip_months=self.skip_months,
            quantile=self.quantile,
            long_short=self.long_short,
            min_price=self.min_price,
        )

    def build_rebalance_policy(self) -> RebalancePolicy:
        """Signals change once a month, so drift between formations is held (REQ-543)."""
        return OnSignalChange()


# A definition's `strategy` field picks the variant; a new strategy is a new
# variant here, never a branch in the runner.
StudyParameters = Annotated[
    TimeSeriesMomentumParameters
    | ShortTermReversalParameters
    | PairsSpreadParameters
    | CrossSectionalMomentumParameters,
    Field(discriminator="strategy"),
]
