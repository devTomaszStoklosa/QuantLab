"""Bars priced in units of cash (q12, REQ-1210..1215)."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from quantlab.core.data.cash import above_cash
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Universe
from quantlab.strategy.time_series_momentum import compute_momentum_signal

_FIRST = date(2020, 1, 1)


def _bars(instrument_id: str, closes: list[float], first: date = _FIRST) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=first + timedelta(days=i),
            open=close * 0.99,
            high=close * 1.01,
            low=close * 0.98,
            close=close,
            volume=1000.0 + i,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def _growing(rate: float, days: int, start: float = 100.0) -> list[float]:
    return [start * (1.0 + rate) ** i for i in range(days)]


def test_an_instrument_growing_like_cash_has_no_return_above_it() -> None:
    cash = _bars("bil", _growing(0.0002, 30, start=90.0))
    bars = {"aaa": _bars("aaa", _growing(0.0002, 30))}

    priced = above_cash(bars, cash)["aaa"]

    assert [bar.close for bar in priced] == pytest.approx([100.0 * 1.0002**29] * 30, rel=1e-12)
    signal = compute_momentum_signal(priced, priced[-1].ts, 10)
    assert signal is not None
    assert signal.strength == pytest.approx(0.0, abs=1e-12)


def test_each_period_returns_the_excess_over_cash() -> None:
    cash_closes = _growing(0.0003, 20, start=50.0)
    closes = [100.0, 101.0, 99.0, 102.5, 102.0] * 4
    cash = _bars("bil", cash_closes)

    priced = above_cash({"aaa": _bars("aaa", closes)}, cash)["aaa"]

    for i in range(1, len(closes)):
        excess = (closes[i] / closes[i - 1]) / (cash_closes[i] / cash_closes[i - 1]) - 1.0
        assert priced[i].close / priced[i - 1].close - 1.0 == pytest.approx(excess, rel=1e-12)


def test_the_series_ends_at_its_quote_and_keeps_volume_and_the_raw_close() -> None:
    closes = _growing(0.001, 10)
    original = _bars("aaa", closes)

    priced = above_cash({"aaa": original}, _bars("bil", _growing(0.0004, 10)))["aaa"]

    assert priced[-1].close == pytest.approx(closes[-1], rel=1e-12)
    # Cash accrued since the first day scales it up: its price in today's cash.
    assert priced[0].close == pytest.approx(closes[0] * 1.0004**9, rel=1e-12)
    assert [bar.volume for bar in priced] == [bar.volume for bar in original]
    assert [bar.raw_close for bar in priced] == closes
    for bar, source in zip(priced, original, strict=True):
        factor = bar.close / source.close
        assert (bar.open, bar.high, bar.low) == pytest.approx(
            (source.open * factor, source.high * factor, source.low * factor), rel=1e-12
        )


def test_bars_before_the_first_cash_bar_are_dropped() -> None:
    bars = {"aaa": _bars("aaa", _growing(0.001, 10))}
    cash = _bars("bil", _growing(0.0002, 7), first=_FIRST + timedelta(days=3))

    priced = above_cash(bars, cash)["aaa"]

    assert [bar.ts for bar in priced] == [_FIRST + timedelta(days=i) for i in range(3, 10)]


def test_a_day_without_cash_takes_the_last_cash_close() -> None:
    cash = [bar for bar in _bars("bil", _growing(0.01, 6)) if bar.ts != _FIRST + timedelta(days=3)]
    closes = [100.0] * 6

    priced = above_cash({"aaa": _bars("aaa", closes)}, cash)["aaa"]

    # Cash earns nothing from day 2 to day 3 (no cash bar on 3), then two days at once.
    assert priced[3].close == pytest.approx(priced[2].close, rel=1e-12)
    assert priced[4].close / priced[3].close == pytest.approx(1.0 / 1.01**2, rel=1e-12)


def test_the_raw_close_survives_a_corporate_action_adjustment() -> None:
    adjusted = [
        PriceBar(
            instrument_id="aaa",
            ts=_FIRST,
            open=50.0,
            high=50.0,
            low=50.0,
            close=50.0,
            volume=1.0,
            source="test",
            unadjusted_close=100.0,
        )
    ]

    priced = above_cash({"aaa": adjusted}, _bars("bil", [80.0]))["aaa"]

    assert priced[0].raw_close == 100.0


def test_there_are_no_returns_above_cash_without_cash_prices() -> None:
    with pytest.raises(ValueError, match="No cash prices"):
        above_cash({"aaa": _bars("aaa", [100.0])}, [])


def _universe(cash: Instrument) -> Universe:
    return Universe(
        name="etfs",
        asof_date=_FIRST,
        source="synthetic",
        periods_per_year=252,
        instruments=[Instrument(id="spy", symbol="SPY", asset_class="equity", quote_asset="USD")],
        market_proxy="spy",
        cash=cash,
    )


def test_a_universe_names_its_cash_outside_its_instruments() -> None:
    universe = _universe(Instrument(id="bil", symbol="BIL", asset_class="cash", quote_asset="USD"))

    assert universe.cash is not None
    assert universe.members(_FIRST) == {"spy"}
    assert [instrument.id for instrument in universe.instruments_between(_FIRST, _FIRST)] == ["spy"]


@pytest.mark.parametrize(
    ("cash", "message"),
    [
        (Instrument(id="spy", symbol="SPY", asset_class="cash", quote_asset="USD"), "also one"),
        (Instrument(id="tlt", symbol="TLT", asset_class="bond", quote_asset="USD"), "class cash"),
    ],
)
def test_cash_is_neither_an_instrument_nor_of_another_class(cash: Instrument, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _universe(cash)
