from typing import Protocol

from quantlab.strategy.signal import Signal


class Sizer(Protocol):
    """Weights of the signals an engine found tradable (REQ-411).

    Engines call it with only the signals whose instruments can trade that
    period, so a sizer decides what a missing instrument means for the rest.
    """

    def weights(self, signals: list[Signal]) -> dict[str, float]: ...


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


class EqualWeightBySign:
    """The default sizer: equal_weight_by_sign."""

    def weights(self, signals: list[Signal]) -> dict[str, float]:
        return equal_weight_by_sign(signals)


class ScaledEqualWeight:
    """Equal weight by sign, each scaled by the weight its signal carries (q11, REQ-1111).

    For signals whose weight is a scale of the equal-weight share, such as
    positions scaled to a target volatility: each of the N tradable non-flat
    signals gets ±weight / N. A scale of 1 is exactly equal_weight_by_sign.
    """

    def weights(self, signals: list[Signal]) -> dict[str, float]:
        active = [signal for signal in signals if signal.direction != "flat"]
        if not active:
            return {}
        if any(signal.weight is None for signal in active):
            raise ValueError("Signals sized by ScaledEqualWeight must carry a weight")
        count = len(active)
        return {
            signal.instrument_id: (signal.weight if signal.direction == "long" else -signal.weight)
            / count
            for signal in active
        }


class CarriedWeights:
    """The signed weights the signals carry, whatever their number (q9, REQ-911).

    For a strategy that has already sized its positions, such as a portfolio
    of sleeves whose net weights arrive as signals: the engines then trade and
    cost exactly those net weights.
    """

    def weights(self, signals: list[Signal]) -> dict[str, float]:
        active = [signal for signal in signals if signal.direction != "flat"]
        if any(signal.weight is None for signal in active):
            raise ValueError("Signals sized by CarriedWeights must carry a weight")
        return {
            signal.instrument_id: signal.weight if signal.direction == "long" else -signal.weight
            for signal in active
        }


class PairWeights:
    """The weights the signals carry, for both legs of a pair or for none (REQ-412).

    A pair with one leg is a directional bet, not a spread, so when the engine
    cannot trade one leg the pair takes no position at all.
    """

    def weights(self, signals: list[Signal]) -> dict[str, float]:
        legs = [signal for signal in signals if signal.direction != "flat"]
        if len(legs) != 2:
            return {}
        if any(leg.weight is None for leg in legs):
            raise ValueError("Pair signals must carry a weight")
        return {
            leg.instrument_id: leg.weight if leg.direction == "long" else -leg.weight
            for leg in legs
        }
