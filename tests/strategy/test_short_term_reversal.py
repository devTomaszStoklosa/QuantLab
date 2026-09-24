from datetime import date, timedelta

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.short_term_reversal import ShortTermReversal, compute_reversal_signal
from quantlab.strategy.time_series_momentum import compute_momentum_signal

_INSTRUMENT_ID = "btc-usdt"


def _bars(start: date, closes: list[float], instrument_id: str = _INSTRUMENT_ID) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=start + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
            adj_close=None,
            source="binance",
        )
        for i, close in enumerate(closes)
    ]


def test_not_enough_history_returns_none() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0])

    assert compute_reversal_signal(bars, as_of=date(2026, 1, 3), formation_days=3) is None


def test_no_bar_for_as_of_returns_none() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0])

    assert compute_reversal_signal(bars, as_of=date(2026, 2, 1), formation_days=3) is None


def test_rise_over_the_formation_period_is_short() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 90.0, 95.0, 110.0])

    signal = compute_reversal_signal(bars, as_of=date(2026, 1, 4), formation_days=3)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.instrument_id == _INSTRUMENT_ID
    assert signal.ts == date(2026, 1, 4)
    assert signal.strength == (110.0 - 100.0) / 100.0


def test_fall_over_the_formation_period_is_long() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 120.0, 105.0, 90.0])

    signal = compute_reversal_signal(bars, as_of=date(2026, 1, 4), formation_days=3)

    assert signal is not None
    assert signal.direction == "long"


def test_zero_formation_return_is_flat() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 130.0, 70.0, 100.0])

    signal = compute_reversal_signal(bars, as_of=date(2026, 1, 4), formation_days=3)

    assert signal is not None
    assert signal.direction == "flat"


def test_only_the_formation_period_matters() -> None:
    # Down over 5 days but up over the last 1: a 1-day formation sees only the rise.
    bars = _bars(date(2026, 1, 1), [100.0, 95.0, 90.0, 85.0, 80.0, 81.0])

    signal = compute_reversal_signal(bars, as_of=date(2026, 1, 6), formation_days=1)

    assert signal is not None
    assert signal.direction == "short"


def test_signal_ignores_data_after_as_of() -> None:
    as_of = date(2026, 1, 4)
    past_bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0])
    future_bars = _bars(date(2026, 1, 5), [50.0, 40.0, 30.0])

    without_future = compute_reversal_signal(past_bars, as_of, formation_days=3)
    with_future = compute_reversal_signal(past_bars + future_bars, as_of, formation_days=3)

    assert without_future == with_future
    assert without_future.direction == "short"


def test_reversal_is_the_opposite_of_momentum_over_the_same_period() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 104.0, 99.0, 103.0, 101.0, 97.0, 102.0])
    opposite = {"long": "short", "short": "long", "flat": "flat"}

    for day in range(3, 7):
        as_of = date(2026, 1, 1) + timedelta(days=day)
        reversal = compute_reversal_signal(bars, as_of, formation_days=3)
        momentum = compute_momentum_signal(bars, as_of, lookback_days=3)
        assert reversal.direction == opposite[momentum.direction]
        assert reversal.strength == momentum.strength


def test_generate_signals_covers_every_instrument_with_enough_history() -> None:
    as_of = date(2026, 1, 4)
    bars = {
        "btc-usdt": _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 110.0], "btc-usdt"),
        "eth-usdt": _bars(date(2026, 1, 1), [50.0, 49.0, 48.0, 40.0], "eth-usdt"),
        "new-listing": _bars(date(2026, 1, 3), [10.0, 11.0], "new-listing"),
    }

    signals = ShortTermReversal(formation_days=3).generate_signals(bars, as_of)

    assert {s.instrument_id: s.direction for s in signals} == {
        "btc-usdt": "short",
        "eth-usdt": "long",
    }
