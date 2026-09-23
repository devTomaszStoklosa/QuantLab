from datetime import date

from quantlab.core.data.provider import PriceBar
from quantlab.core.storage import read_price_bars, write_price_bars

_INSTRUMENT_ID = "btc-usdt"


def _bar(day: date, close: float) -> PriceBar:
    return PriceBar(
        instrument_id=_INSTRUMENT_ID,
        ts=day,
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=123.456789,
        adj_close=None,
        source="binance",
    )


def test_read_returns_empty_list_when_nothing_written(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    bars = read_price_bars(_INSTRUMENT_ID, date(2026, 1, 1), date(2026, 1, 31))

    assert bars == []


def test_write_then_read_round_trips_without_precision_loss(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    original = _bar(date(2026, 9, 20), 86620.123456789)

    write_price_bars([original])
    bars = read_price_bars(_INSTRUMENT_ID, date(2026, 9, 20), date(2026, 9, 20))

    assert len(bars) == 1
    assert bars[0] == original


def test_read_filters_by_date_range(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_price_bars(
        [_bar(date(2026, 9, 19), 100.0), _bar(date(2026, 9, 20), 101.0), _bar(date(2026, 9, 21), 102.0)]
    )

    bars = read_price_bars(_INSTRUMENT_ID, date(2026, 9, 20), date(2026, 9, 20))

    assert [bar.ts for bar in bars] == [date(2026, 9, 20)]


def test_write_twice_upserts_by_date_instead_of_duplicating(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    write_price_bars([_bar(date(2026, 9, 20), 100.0)])
    write_price_bars([_bar(date(2026, 9, 20), 999.0), _bar(date(2026, 9, 21), 200.0)])

    bars = read_price_bars(_INSTRUMENT_ID, date(2026, 9, 20), date(2026, 9, 21))

    assert [bar.close for bar in bars] == [999.0, 200.0]
