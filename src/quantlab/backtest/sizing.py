from quantlab.strategy.signal import Signal


def equal_weight_by_sign(signals: list[Signal]) -> dict[str, float]:
    """Equal weight among the non-flat signals, signed by direction.

    Weighting is by sign only, not `signal.strength` - that field is an
    unnormalized per-instrument return (see time_series_momentum.py) and isn't
    comparable across instruments. Callers pass only the signals that can be
    traded; the rule itself is shared by both engines (REQ-203).
    """
    active = [signal for signal in signals if signal.direction != "flat"]
    if not active:
        return {}
    magnitude = 1.0 / len(active)
    return {
        signal.instrument_id: magnitude if signal.direction == "long" else -magnitude
        for signal in active
    }
