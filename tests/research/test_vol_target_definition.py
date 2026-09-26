from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from quantlab.backtest.sizing import ScaledEqualWeight
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Universe
from quantlab.reporting.volatility_scaling import CONTRAST_TITLE, SCALE_TITLE
from quantlab.research.definition import (
    StudyParameters,
    VolatilityTargetedMomentumParameters,
)
from quantlab.risk.volatility import EwmaVolatility, RollingVolatility
from quantlab.strategy.volatility_target import VolatilityTargeted

_FIRST = date(2017, 1, 1)
_LAST = date(2019, 12, 31)
_START = date(2018, 1, 1)


def _parameters(**changes) -> VolatilityTargetedMomentumParameters:
    fields = {
        "strategy": "time_series_momentum_vol_target",
        "lookback_days": 90,
        "target_volatility": 0.4,
        "max_scale": 1.0,
        "volatility": {"estimator": "ewma", "center_of_mass_days": 20, "window_days": 120},
        "universe": "mvp-crypto",
        "cost_model": {"name": "realistic", "fee_bps": 10, "k": 0.05, "vol_window": 30},
    } | changes
    parsed = TypeAdapter(StudyParameters).validate_python(fields)
    assert isinstance(parsed, VolatilityTargetedMomentumParameters)
    return parsed


def _bars() -> dict[str, list[PriceBar]]:
    """BTC and ETH with trends turning every 90 days and volatility changing every 120."""
    rng = np.random.default_rng(4)
    days = (_LAST - _FIRST).days
    drift = np.repeat(rng.choice([-0.003, 0.003], size=days // 90 + 1), 90)[:days]
    volatility = np.repeat(np.resize([0.01, 0.06, 0.03], days // 120 + 1), 120)[:days]
    bars = {}
    for instrument_id in ("btc-usdt", "eth-usdt"):
        returns = drift + volatility * rng.normal(0.0, 1.0, days)
        closes = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + returns]))
        bars[instrument_id] = [
            PriceBar(
                instrument_id=instrument_id,
                ts=_FIRST + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(closes)
        ]
    return bars


def test_the_definition_builds_scaled_momentum_with_its_estimator() -> None:
    parameters = _parameters()

    strategy = parameters.build_strategy()

    assert isinstance(strategy, VolatilityTargeted)
    assert isinstance(strategy.estimator, EwmaVolatility)
    assert strategy.estimator.center_of_mass_days == 20
    assert isinstance(parameters.build_sizer(), ScaledEqualWeight)
    assert parameters.strategy_params() == {
        "lookback_days": 90,
        "target_volatility": 0.4,
        "max_scale": 1.0,
        "volatility": {"estimator": "ewma", "window_days": 120, "center_of_mass_days": 20.0},
    }
    rolling = _parameters(volatility={"estimator": "rolling", "window_days": 60})
    assert isinstance(rolling.build_strategy().estimator, RollingVolatility)


def test_the_warm_up_covers_the_signal_and_the_estimator() -> None:
    assert _parameters().warm_up_days == 120
    assert _parameters(lookback_days=365).warm_up_days == 365


@pytest.mark.parametrize(
    "changes",
    [
        {"max_scale": 1.5},
        {"max_scale": 0.0},
        {"target_volatility": 0.0},
        {"volatility": {"estimator": "garch", "window_days": 60}},
        {"volatility": {"estimator": "ewma", "window_days": 60}},  # no center of mass
        {"volatility": {"estimator": "rolling", "window_days": 1}},
    ],
)
def test_leverage_and_incomplete_estimators_are_refused(changes) -> None:
    with pytest.raises(ValidationError):
        _parameters(**changes)


def test_the_first_holdout_day_sees_what_a_longer_history_would() -> None:
    parameters = _parameters()
    bars = _bars()
    start = date(2019, 6, 1)
    fetched = {
        instrument_id: [
            bar
            for bar in series
            if bar.ts >= parameters.fetch_start(start, Universe.load(parameters.universe))
        ]
        for instrument_id, series in bars.items()
    }

    strategy = parameters.build_strategy()

    assert strategy.generate_signals(fetched, start) == strategy.generate_signals(bars, start)
    assert all(signal.weight is not None for signal in strategy.generate_signals(fetched, start))


def test_the_diagnostics_show_the_scales_and_the_unscaled_contrast() -> None:
    diagnostics = {
        diagnostic.title: diagnostic.values
        for diagnostic in _parameters().training_diagnostics(_bars(), _START, _LAST)
    }

    scales, contrast = diagnostics[SCALE_TITLE], diagnostics[CONTRAST_TITLE]
    assert list(scales) == [
        f"{instrument_id} {label}"
        for instrument_id in ("btc-usdt", "eth-usdt")
        for label in ("mean", "min", "max", "share at the cap")
    ]
    assert scales["btc-usdt max"] == 1.0
    assert 0.0 < scales["btc-usdt min"] < scales["btc-usdt mean"] < 1.0
    assert 0.0 < scales["btc-usdt share at the cap"] < 1.0
    assert contrast["volatility scaled"] < contrast["volatility unscaled"]
    assert contrast["max drawdown unscaled"] <= contrast["max drawdown scaled"] <= 0.0


def test_at_the_cap_every_day_both_sides_of_the_contrast_agree() -> None:
    diagnostics = {
        diagnostic.title: diagnostic.values
        for diagnostic in _parameters(target_volatility=1e6).training_diagnostics(
            _bars(), _START, _LAST
        )
    }

    contrast = diagnostics[CONTRAST_TITLE]
    assert contrast["Sharpe scaled"] == contrast["Sharpe unscaled"]
    assert diagnostics[SCALE_TITLE]["eth-usdt share at the cap"] == 1.0


def test_without_a_window_every_value_is_missing() -> None:
    bars = _bars()
    short = {instrument_id: series[:100] for instrument_id, series in bars.items()}

    diagnostics = _parameters().training_diagnostics(short, _START, _LAST)

    assert all(value is None for diagnostic in diagnostics for value in diagnostic.values.values())
