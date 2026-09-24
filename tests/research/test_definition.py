from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from quantlab.backtest.sizing import EqualWeightBySign, PairWeights
from quantlab.core.data.provider import PriceBar
from quantlab.research.definition import (
    CostModelParameters,
    PairsSpreadParameters,
    ShortTermReversalParameters,
    TimeSeriesMomentumParameters,
)
from quantlab.strategy.pairs_spread import PairsSpreadReversion
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


def _pairs(**changes: object) -> PairsSpreadParameters:
    fields = {
        "strategy": "pairs_spread",
        "dependent": "eth-usdt",
        "explanatory": "btc-usdt",
        "formation_days": 365,
        "entry_z": 2.0,
        "exit_z": 0.0,
        "max_coint_p_value": 0.05,
        "universe": "mvp-crypto",
        "cost_model": _COST_MODEL,
    }
    return PairsSpreadParameters(**(fields | changes))


def test_pairs_parameters_build_their_strategy_and_pair_sizer() -> None:
    parameters = _pairs()

    strategy = parameters.build_strategy()

    assert isinstance(strategy, PairsSpreadReversion)
    assert (strategy.dependent, strategy.explanatory) == ("eth-usdt", "btc-usdt")
    assert strategy.max_coint_p_value == 0.05
    assert isinstance(parameters.build_sizer(), PairWeights)
    assert parameters.warm_up_days == 365
    assert parameters.strategy_params()["entry_z"] == 2.0


@pytest.mark.parametrize(
    "changes",
    [
        {"explanatory": "eth-usdt"},
        {"exit_z": 2.0},
        {"formation_days": 20},
        {"entry_z": 0.0},
        {"max_coint_p_value": 1.0},
    ],
)
def test_pairs_parameters_reject_inconsistent_values(changes: dict) -> None:
    with pytest.raises(ValidationError):
        _pairs(**changes)


def test_the_cointegration_filter_must_be_stated_even_when_off() -> None:
    assert _pairs(max_coint_p_value=None).build_strategy().max_coint_p_value is None
    fields = _pairs().model_dump()
    del fields["max_coint_p_value"]
    with pytest.raises(ValidationError):
        PairsSpreadParameters(**fields)


def test_a_pairs_definition_parses_through_the_strategy_field() -> None:
    config = HoldoutConfig.model_validate(_definition(_pairs().model_dump(mode="json")))

    assert isinstance(config.parameters, PairsSpreadParameters)


def _log_price_bars(instrument_id: str, log_prices: np.ndarray) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=date(2020, 1, 1) + timedelta(days=i),
            open=float(np.exp(v)),
            high=float(np.exp(v)),
            low=float(np.exp(v)),
            close=float(np.exp(v)),
            volume=1.0,
            source="test",
        )
        for i, v in enumerate(log_prices)
    ]


def test_pairs_report_cointegration_over_the_training_period_only() -> None:
    rng = np.random.default_rng(8)
    log_x = 10.0 + np.cumsum(rng.normal(0.0, 0.03, 900))
    spread = np.zeros(900)
    for t in range(1, 900):
        spread[t] = 0.9 * spread[t - 1] + rng.normal(0.0, 0.01)
    log_y = 0.5 + 0.8 * log_x + spread
    log_y[700:] += np.linspace(0.0, 3.0, 200)  # breaks down after the training period
    bars = {
        "eth-usdt": _log_price_bars("eth-usdt", log_y),
        "btc-usdt": _log_price_bars("btc-usdt", log_x),
    }

    (diagnostic,) = _pairs().training_diagnostics(bars, date(2020, 1, 1), date(2021, 11, 30))

    assert diagnostic.title == "Cointegration of eth-usdt on btc-usdt"
    assert diagnostic.values["days"] == 700
    assert diagnostic.values["hedge ratio"] == pytest.approx(0.8, abs=0.03)
    assert diagnostic.values["p-value"] < 0.01
    assert diagnostic.values["half-life (days)"] == pytest.approx(6.6, rel=0.3)


def test_directional_strategies_report_no_training_diagnostics() -> None:
    assert _momentum().training_diagnostics({}, date(2020, 1, 1), date(2021, 1, 1)) == []
