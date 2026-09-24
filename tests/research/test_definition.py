import pytest
from pydantic import ValidationError

from quantlab.research.definition import CostModelParameters, TimeSeriesMomentumParameters
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


def test_unknown_strategy_is_refused_when_a_definition_is_read() -> None:
    definition = {
        "hypothesis": "x_v1",
        "training_start": "2018-01-01",
        "training_end": "2023-12-31",
        "start": "2024-01-01",
        "end": "2025-12-31",
        "parameters": {
            "strategy": "no_such_strategy",
            "lookback_days": 365,
            "universe": "mvp-crypto",
            "cost_model": _COST_MODEL.model_dump(),
        },
        "success_criterion": {"description": "d", "min_sharpe": 0.0, "max_p_value": 0.1},
    }

    with pytest.raises(ValidationError):
        HoldoutConfig.model_validate(definition)
