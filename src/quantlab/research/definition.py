"""Hypothesis definitions: which strategy, with which parameters, on what, at what cost.

The committed frozen file (config/holdout/<id>.yaml) is the single definition
of a hypothesis (q3 03-design, Option A), so every run reads its parameters
from there. Each strategy's parameters are their own model and build their
own strategy: the runner never branches on the strategy type (REQ-301).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated, Literal, Protocol, Self

import numpy as np
from pydantic import BaseModel, Field, PrivateAttr, model_validator

from quantlab.backtest.rebalance import Daily, OnSignalChange, RebalancePolicy
from quantlab.backtest.sizing import (
    CarriedWeights,
    EqualWeightBySign,
    PairWeights,
    ScaledEqualWeight,
    Sizer,
)
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Universe
from quantlab.costs.realistic import RealisticCostModel
from quantlab.portfolio.allocation import ALLOCATION_RULES
from quantlab.portfolio.report import portfolio_report
from quantlab.reporting.volatility_scaling import scaling_report
from quantlab.risk.volatility import EwmaVolatility, RollingVolatility, VolatilityEstimator
from quantlab.strategy.base import Strategy
from quantlab.strategy.cointegration import engle_granger
from quantlab.strategy.cross_sectional_momentum import CrossSectionalMomentum
from quantlab.strategy.pairs_spread import PairsSpreadReversion
from quantlab.strategy.portfolio import Sleeve, SleeveHistory, StrategyPortfolio
from quantlab.strategy.selected_parameter import (
    SelectedParameter,
    SelectionRecord,
    common_start,
    net_returns,
)
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.strategy.volatility_target import VolatilityTargeted


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


@dataclass(frozen=True)
class GridEvidence:
    """What a hypothesis choosing its parameter from a grid shows besides its run (q8)."""

    labels: list[str]  # grid values, in grid order
    start: date  # first day of the window every value can signal in
    end: date
    returns: np.ndarray  # T x K net daily returns of each value over the window
    history: list[SelectionRecord]  # the yearly choices over the run's window


class ComponentDefinition(Protocol):
    """What a definition referring to other hypotheses reads of each (a HoldoutConfig)."""

    hypothesis: str
    start: date  # its holdout
    end: date

    @property
    def parameters(self) -> "StudyParametersBase": ...


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

    def fetch_start(self, start: date) -> date:
        """The first day of data a run over a window starting on `start` needs."""
        return start - timedelta(days=self.warm_up_days)

    @property
    def configurations(self) -> int:
        """Parameter configurations this hypothesis tries on its data (q8, REQ-820): 1
        for fixed parameters, the grid's size when one is chosen from a grid."""
        return 1

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

    def grid_evidence(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> GridEvidence | None:
        """The grid's returns and choices over [start, end]; None without a grid (q8)."""
        return None

    def resolve(self, load: Callable[[str], ComponentDefinition]) -> Self:
        """This definition with the frozen definitions it refers to loaded by `load`
        (q9, REQ-920); itself for a hypothesis that refers to none. The runner calls it
        on every definition it loads, never asking what kind it is."""
        return self

    def holdout_prerequisites(self, start: date, end: date) -> list[str]:
        """Hypotheses whose one-time holdout opening must be recorded before a holdout
        [start, end] of this one may be opened (q9, REQ-930); none by default."""
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


class TimeSeriesMomentumSelectedParameters(StudyParametersBase):
    """Time-series momentum whose lookback is chosen each year on past data (q8, REQ-801).

    The frozen hypothesis is the procedure, not a lookback: the grid, the
    anchored history from `history_start` and the minimum history before a first
    choice; each year's value is the one with the best net Sharpe under this
    definition's cost model on the bars before that year (SelectedParameter).
    """

    strategy: Literal["time_series_momentum_selected"]
    lookback_grid: list[int] = Field(min_length=2)
    history_start: date
    min_history_days: int = Field(ge=1)

    @model_validator(mode="after")
    def _grid(self) -> Self:
        if len(set(self.lookback_grid)) != len(self.lookback_grid):
            raise ValueError("lookback_grid must not repeat a value")
        if self.lookback_grid != sorted(self.lookback_grid) or self.lookback_grid[0] < 1:
            raise ValueError("lookback_grid must be ascending lookbacks of at least 1 day")
        return self

    @property
    def warm_up_days(self) -> int:
        return max(self.lookback_grid)

    def fetch_start(self, start: date) -> date:
        # The choices read the anchored history, and its first day needs the longest warm-up.
        return min(start, self.history_start) - timedelta(days=self.warm_up_days)

    @property
    def configurations(self) -> int:
        return len(self.lookback_grid)

    def strategy_params(self) -> dict:
        return {
            "lookback_grid": self.lookback_grid,
            "history_start": self.history_start.isoformat(),
            "min_history_days": self.min_history_days,
        }

    def grid_evidence(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> GridEvidence | None:
        """One backtest per lookback over the window all of them can signal in, under
        this definition's cost model (REQ-813), and the procedure's yearly choices."""
        window_start = common_start(bars, self.warm_up_days, start)
        if window_start is None or window_start > end:
            raise ValueError(f"No window between {start} and {end} in which every lookback signals")
        cost_model = self.cost_model.build()
        returns = np.array(
            [
                net_returns(TimeSeriesMomentum(lookback), cost_model, bars, window_start, end)
                for lookback in self.lookback_grid
            ]
        ).T
        selection = self.build_strategy()
        return GridEvidence(
            labels=[str(lookback) for lookback in self.lookback_grid],
            start=window_start,
            end=end,
            returns=returns,
            history=[selection.choice(bars, year) for year in range(start.year, end.year + 1)],
        )

    def build_strategy(self) -> Strategy:
        return SelectedParameter(
            variants={
                str(lookback): lambda lookback=lookback: TimeSeriesMomentum(lookback_days=lookback)
                for lookback in self.lookback_grid
            },
            cost_model=self.cost_model.build(),
            warm_up_days=self.warm_up_days,
            history_start=self.history_start,
            min_history_days=self.min_history_days,
        )


class StrategyPortfolioParameters(StudyParametersBase):
    """A portfolio of frozen hypotheses traded as net positions (q9, REQ-910..923).

    The frozen hypothesis is the rule for combining them: the components (by
    hypothesis id, each traded as its own frozen definition trades it), the
    allocation rule, the estimation window and the anchor of the sleeves'
    history; weights change on the first day of each month. The components are
    loaded by `resolve`, through the same path as any run's definition, so a
    component changed or deleted after freezing stops the run.
    """

    strategy: Literal["strategy_portfolio"]
    components: list[str] = Field(min_length=2)
    allocation: str
    window_days: int = Field(ge=2)
    min_window_days: int = Field(ge=2)
    history_start: date
    _definitions: dict[str, ComponentDefinition] | None = PrivateAttr(default=None)
    _history: SleeveHistory | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _rule(self) -> Self:
        if len(set(self.components)) != len(self.components):
            raise ValueError("components must not repeat")
        if self.allocation not in ALLOCATION_RULES:
            raise ValueError(
                f"Unknown allocation {self.allocation!r}; one of {sorted(ALLOCATION_RULES)}"
            )
        return self

    def resolve(self, load: Callable[[str], ComponentDefinition]) -> Self:
        definitions = {name: load(name) for name in self.components}
        for name, definition in definitions.items():
            parameters = definition.parameters
            if parameters.strategy == self.strategy:
                raise ValueError(f"Component {name} is itself a portfolio")
            if parameters.universe != self.universe:
                raise ValueError(
                    f"Component {name} trades {parameters.universe}, the portfolio {self.universe}"
                )
        resolved = self.model_copy()
        resolved._definitions = definitions
        resolved._history = None
        return resolved

    def _loaded(self) -> dict[str, ComponentDefinition]:
        if self._definitions is None:
            raise ValueError("The portfolio's components are not loaded: resolve() it first")
        return self._definitions

    @property
    def warm_up_days(self) -> int:
        return max(definition.parameters.warm_up_days for definition in self._loaded().values())

    def fetch_start(self, start: date) -> date:
        # The sleeves' history starts at the anchor, and each sleeve needs its own warm-up.
        anchor = min(start, self.history_start)
        return min(
            definition.parameters.fetch_start(anchor) for definition in self._loaded().values()
        )

    def strategy_params(self) -> dict:
        return {
            "components": self.components,
            "allocation": self.allocation,
            "window_days": self.window_days,
            "min_window_days": self.min_window_days,
            "history_start": self.history_start.isoformat(),
        }

    def sleeve_history(self) -> SleeveHistory:
        """The sleeves' returns before each rebalance day, shared by every strategy this
        definition builds (cost models, engines, stress scenarios alike)."""
        if self._history is None:
            self._history = SleeveHistory(
                [
                    Sleeve(
                        name=name,
                        build=definition.parameters.build_strategy,
                        sizer=definition.parameters.build_sizer(),
                        rebalance=definition.parameters.build_rebalance_policy(),
                        cost_model=definition.parameters.cost_model.build(),
                    )
                    for name, definition in self._loaded().items()
                ],
                self.history_start,
            )
        return self._history

    def build_strategy(self) -> Strategy:
        return StrategyPortfolio(
            self.sleeve_history(),
            ALLOCATION_RULES[self.allocation],
            self.window_days,
            self.min_window_days,
        )

    def build_sizer(self) -> Sizer:
        return CarriedWeights()

    def training_diagnostics(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> list[TrainingDiagnostic]:
        """Sleeve correlations, the frozen rule's weights and diversification ratio, and
        the net Sharpe under each rule and of each sleeve alone (REQ-940, REQ-941)."""
        report = portfolio_report(
            history=self.sleeve_history(),
            rules=ALLOCATION_RULES,
            frozen=self.allocation,
            window_days=self.window_days,
            min_window_days=self.min_window_days,
            cost_model=self.cost_model.build(),
            bars=bars,
            start=start,
            end=end,
            periods_per_year=Universe.load(self.universe).periods_per_year,
        )
        return [TrainingDiagnostic(title=title, values=values) for title, values in report.items()]

    def holdout_prerequisites(self, start: date, end: date) -> list[str]:
        return [
            name
            for name, definition in self._loaded().items()
            if definition.start <= end and start <= definition.end
        ]


class RollingVolatilityParameters(BaseModel):
    """Realized volatility: the sample standard deviation of the window's returns."""

    estimator: Literal["rolling"]
    window_days: int = Field(ge=2)

    def build(self) -> VolatilityEstimator:
        return RollingVolatility(window_days=self.window_days)


class EwmaVolatilityParameters(BaseModel):
    """Exponentially weighted volatility over the window (Moskowitz, Ooi, Pedersen 2012)."""

    estimator: Literal["ewma"]
    window_days: int = Field(ge=2)
    center_of_mass_days: float = Field(gt=0)

    def build(self) -> VolatilityEstimator:
        return EwmaVolatility(
            center_of_mass_days=self.center_of_mass_days, window_days=self.window_days
        )


# The `estimator` field picks the model, and each builds its own estimator (REQ-1103).
VolatilityParameters = Annotated[
    RollingVolatilityParameters | EwmaVolatilityParameters, Field(discriminator="estimator")
]


class VolatilityTargetedMomentumParameters(StudyParametersBase):
    """Time-series momentum with positions scaled to a target volatility (q11, REQ-1120).

    The signal is momentum_v1's; only the position size differs: each instrument's
    equal-weight share times min(max_scale, target / annualized ex-ante volatility),
    with max_scale at most 1, so there is no borrowing the engines would not cost.
    """

    strategy: Literal["time_series_momentum_vol_target"]
    lookback_days: int = Field(ge=1)
    target_volatility: float = Field(gt=0)
    max_scale: float = Field(gt=0, le=1)
    volatility: VolatilityParameters

    @property
    def warm_up_days(self) -> int:
        # The estimator reads its whole window inside the warm-up, so a holdout's
        # first estimate is the one a longer history would give (REQ-1121).
        return max(self.lookback_days, self.volatility.window_days)

    def strategy_params(self) -> dict:
        return {
            "lookback_days": self.lookback_days,
            "target_volatility": self.target_volatility,
            "max_scale": self.max_scale,
            "volatility": self.volatility.model_dump(),
        }

    def build_strategy(self) -> VolatilityTargeted:
        return VolatilityTargeted(
            inner=TimeSeriesMomentum(lookback_days=self.lookback_days),
            estimator=self.volatility.build(),
            target_volatility=self.target_volatility,
            max_scale=self.max_scale,
            periods_per_year=Universe.load(self.universe).periods_per_year,
        )

    def build_sizer(self) -> Sizer:
        return ScaledEqualWeight()

    def training_diagnostics(
        self, bars: dict[str, list[PriceBar]], start: date, end: date
    ) -> list[TrainingDiagnostic]:
        """The scales per instrument, and the same momentum unscaled over the same
        window and cost model (REQ-1130)."""
        report = scaling_report(
            scaled=self.build_strategy(),
            sizer=self.build_sizer(),
            unscaled=TimeSeriesMomentum(lookback_days=self.lookback_days),
            cost_model=self.cost_model.build(),
            bars=bars,
            start=common_start(bars, self.warm_up_days, start),
            end=end,
            periods_per_year=Universe.load(self.universe).periods_per_year,
        )
        return [TrainingDiagnostic(title=title, values=values) for title, values in report.items()]


# A definition's `strategy` field picks the variant; a new strategy is a new
# variant here, never a branch in the runner.
StudyParameters = Annotated[
    TimeSeriesMomentumParameters
    | ShortTermReversalParameters
    | PairsSpreadParameters
    | CrossSectionalMomentumParameters
    | TimeSeriesMomentumSelectedParameters
    | StrategyPortfolioParameters
    | VolatilityTargetedMomentumParameters,
    Field(discriminator="strategy"),
]
