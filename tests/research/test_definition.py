import pytest
from pydantic import ValidationError

from quantlab.backtest.sizing import EqualWeightBySign
from quantlab.research.definition import (
    CostModelParameters,
    ShortTermReversalParameters,
    TimeSeriesMomentumParameters,
)
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.validation.holdout import HoldoutConfig

_COST_MODEL = CostModelParameters(name="realistic", fee_bps=10, k=0.05, vol_window=30)


def _momentum(lookback_days: int = 365) -> TimeSeriesMomentumParameters:
    return TimeSeriesMomentumParameters(
        strategy="time_series_momentum",
        lookback_days=lookback_days,
        universe="mvp-crypto",
        cost_model=_COST_MODEL,
    )


def test_momentum_parameters_build_their_own_strategy() -> None:
    parameters = _momentum(lookback_days=90)

    strategy = parameters.build_strategy()

    assert isinstance(strategy, TimeSeriesMomentum)
    assert strategy.lookback_days == 90
    assert parameters.warm_up_days == 90
    assert parameters.strategy_params() == {"lookback_days": 90}


def test_cost_model_parameters_build_the_realistic_model() -> None:
    model = _COST_MODEL.build()

    assert model.name == "realistic-10bps-k0.05-vol30d"


def test_lookback_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        _momentum(lookback_days=0)


def _definition(parameters: dict) -> dict:
    return {
        "hypothesis": "x_v1",
        "training_start": "2018-01-01",
        "training_end": "2023-12-31",
        "start": "2024-01-01",
        "end": "2025-12-31",
        "parameters": {
            "universe": "mvp-crypto",
            "cost_model": _COST_MODEL.model_dump(),
            **parameters,
        },
        "success_criterion": {"description": "d", "min_sharpe": 0.0, "max_p_value": 0.1},
    }


def test_reversal_parameters_build_their_own_strategy() -> None:
    parameters = ShortTermReversalParameters(
        strategy="short_term_reversal",
        formation_days=7,
        universe="mvp-crypto",
        cost_model=_COST_MODEL,
    )

    strategy = parameters.build_strategy()

    assert isinstance(strategy, ShortTermReversal)
    assert strategy.formation_days == 7
    assert parameters.warm_up_days == 7
    assert parameters.strategy_params() == {"formation_days": 7}


def test_formation_period_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ShortTermReversalParameters(
            strategy="short_term_reversal", formation_days=0, universe="u", cost_model=_COST_MODEL
        )


def test_a_definition_picks_its_parameters_by_strategy() -> None:
    momentum = HoldoutConfig.model_validate(
        _definition({"strategy": "time_series_momentum", "lookback_days": 365})
    )
    reversal = HoldoutConfig.model_validate(
        _definition({"strategy": "short_term_reversal", "formation_days": 7})
    )

    assert isinstance(momentum.parameters, TimeSeriesMomentumParameters)
    assert isinstance(reversal.parameters, ShortTermReversalParameters)
    assert reversal.parameters.formation_days == 7


def test_parameters_of_another_strategy_are_refused() -> None:
    with pytest.raises(ValidationError):
        HoldoutConfig.model_validate(
            _definition({"strategy": "short_term_reversal", "lookback_days": 365})
        )


def test_unknown_strategy_is_refused_when_a_definition_is_read() -> None:
    with pytest.raises(ValidationError):
        HoldoutConfig.model_validate(
            _definition({"strategy": "no_such_strategy", "lookback_days": 365})
        )


def test_existing_strategies_are_sized_equally_by_sign() -> None:
    reversal = ShortTermReversalParameters(
        strategy="short_term_reversal",
        formation_days=7,
        universe="mvp-crypto",
        cost_model=_COST_MODEL,
    )

    assert isinstance(_momentum().build_sizer(), EqualWeightBySign)
    assert isinstance(reversal.build_sizer(), EqualWeightBySign)
