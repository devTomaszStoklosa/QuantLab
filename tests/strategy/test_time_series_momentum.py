from datetime import date, timedelta

from quantlab.core.data.provider import PriceBar
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum, compute_momentum_signal

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

    signal = compute_momentum_signal(bars, as_of=date(2026, 1, 3), lookback_days=5)

    assert signal is None


def test_no_bar_for_as_of_returns_none() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0, 104.0, 105.0])

    signal = compute_momentum_signal(bars, as_of=date(2026, 2, 1), lookback_days=5)

    assert signal is None


def test_positive_lookback_return_is_long() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0, 104.0, 110.0])

    signal = compute_momentum_signal(bars, as_of=date(2026, 1, 6), lookback_days=5)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.strength == (110.0 - 100.0) / 100.0


def test_negative_lookback_return_is_short() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 99.0, 98.0, 97.0, 96.0, 90.0])

    signal = compute_momentum_signal(bars, as_of=date(2026, 1, 6), lookback_days=5)

    assert signal is not None
    assert signal.direction == "short"


def test_zero_lookback_return_is_flat() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 105.0, 95.0, 110.0, 90.0, 100.0])

    signal = compute_momentum_signal(bars, as_of=date(2026, 1, 6), lookback_days=5)

    assert signal is not None
    assert signal.direction == "flat"


def test_signal_ignores_data_after_as_of() -> None:
    as_of = date(2026, 1, 6)
    past_bars = _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0, 104.0, 110.0])
    future_bars = _bars(date(2026, 1, 7), [50.0, 40.0, 30.0])

    signal_without_future = compute_momentum_signal(past_bars, as_of, lookback_days=5)
    signal_with_future = compute_momentum_signal(past_bars + future_bars, as_of, lookback_days=5)

    assert signal_without_future == signal_with_future
    assert signal_without_future.direction == "long"


def test_generate_signals_covers_every_instrument_with_enough_history() -> None:
    as_of = date(2026, 1, 6)
    bars = {
        "btc-usdt": _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0, 104.0, 110.0], "btc-usdt"),
        "eth-usdt": _bars(date(2026, 1, 1), [50.0, 49.0, 48.0, 47.0, 46.0, 40.0], "eth-usdt"),
    }
    strategy = TimeSeriesMomentum(lookback_days=5)

    signals = strategy.generate_signals(bars, as_of)

    assert {s.instrument_id: s.direction for s in signals} == {
        "btc-usdt": "long",
        "eth-usdt": "short",
    }


def test_generate_signals_skips_instrument_with_too_little_history() -> None:
    as_of = date(2026, 1, 6)
    bars = {
        "btc-usdt": _bars(date(2026, 1, 1), [100.0, 101.0, 102.0, 103.0, 104.0, 110.0], "btc-usdt"),
        "new-listing": _bars(date(2026, 1, 5), [10.0, 11.0], "new-listing"),
    }
    strategy = TimeSeriesMomentum(lookback_days=5)

    signals = strategy.generate_signals(bars, as_of)

    assert [s.instrument_id for s in signals] == ["btc-usdt"]
