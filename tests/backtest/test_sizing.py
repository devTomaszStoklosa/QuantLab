from datetime import date

from quantlab.backtest.sizing import equal_weight_by_sign
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
