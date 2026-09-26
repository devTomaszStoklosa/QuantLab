from datetime import date

import pytest

from quantlab.backtest.sizing import (
    EqualWeightBySign,
    PairWeights,
    ScaledEqualWeight,
    equal_weight_by_sign,
)
from quantlab.strategy.signal import Signal

_DAY = date(2026, 1, 1)


def _signal(instrument_id: str, direction: str, strength: float = 0.0) -> Signal:
    return Signal(instrument_id=instrument_id, ts=_DAY, direction=direction, strength=strength)


def test_weights_are_equal_in_size_and_signed_by_direction() -> None:
    weights = equal_weight_by_sign([_signal("a", "long"), _signal("b", "short")])

    assert weights == {"a": 0.5, "b": -0.5}


def test_flat_signals_take_no_weight_and_do_not_dilute_the_others() -> None:
    weights = equal_weight_by_sign(
        [_signal("a", "long"), _signal("b", "flat"), _signal("c", "long")]
    )

    assert weights == {"a": 0.5, "c": 0.5}


def test_strength_does_not_change_the_weight() -> None:
    weights = equal_weight_by_sign([_signal("a", "long", 0.9), _signal("b", "long", 0.01)])

    assert weights == {"a": 0.5, "b": 0.5}


def test_no_active_signal_gives_no_weights() -> None:
    assert equal_weight_by_sign([]) == {}
    assert equal_weight_by_sign([_signal("a", "flat")]) == {}


def _leg(instrument_id: str, direction: str, weight: float | None) -> Signal:
    return Signal(
        instrument_id=instrument_id, ts=_DAY, direction=direction, strength=0.0, weight=weight
    )


def test_equal_weight_sizer_is_the_shared_rule() -> None:
    signals = [_signal("a", "long"), _signal("b", "short"), _signal("c", "flat")]

    assert EqualWeightBySign().weights(signals) == equal_weight_by_sign(signals)


def test_pair_weights_come_from_the_signals_with_their_direction() -> None:
    weights = PairWeights().weights([_leg("eth", "long", 0.55), _leg("btc", "short", 0.45)])

    assert weights == {"eth": 0.55, "btc": -0.45}


def test_a_pair_trades_both_legs_or_none() -> None:
    sizer = PairWeights()

    assert sizer.weights([_leg("eth", "long", 0.55)]) == {}
    assert sizer.weights([_leg("eth", "long", 0.55), _leg("btc", "flat", None)]) == {}
    assert sizer.weights([]) == {}
    three = [_leg("a", "long", 0.3), _leg("b", "short", 0.3), _leg("c", "long", 0.4)]
    assert sizer.weights(three) == {}


def test_pair_signals_without_a_weight_are_an_error() -> None:
    with pytest.raises(ValueError, match="carry a weight"):
        PairWeights().weights([_leg("eth", "long", None), _leg("btc", "short", 0.45)])


def test_a_signal_weight_must_be_positive() -> None:
    with pytest.raises(ValueError):
        _leg("eth", "long", 0.0)


def _scaled(instrument_id: str, direction: str, weight: float | None) -> Signal:
    return Signal(
        instrument_id=instrument_id, ts=_DAY, direction=direction, strength=0.0, weight=weight
    )


def test_scaled_equal_weight_splits_each_scale_among_the_tradable_signals() -> None:
    weights = ScaledEqualWeight().weights(
        [_scaled("a", "long", 0.5), _scaled("b", "short", 0.8), _scaled("c", "flat", None)]
    )

    assert weights == {"a": 0.25, "b": -0.4}


def test_a_scale_of_one_is_equal_weight_by_sign() -> None:
    signals = [_scaled("a", "long", 1.0), _scaled("b", "short", 1.0), _scaled("c", "long", 1.0)]

    assert ScaledEqualWeight().weights(signals) == equal_weight_by_sign(signals)


def test_scaled_equal_weight_needs_a_scale_on_every_active_signal() -> None:
    assert ScaledEqualWeight().weights([_scaled("a", "flat", None)]) == {}
    with pytest.raises(ValueError, match="must carry a weight"):
        ScaledEqualWeight().weights([_scaled("a", "long", None)])
