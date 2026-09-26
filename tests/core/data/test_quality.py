"""The lab's checks of the bars a run uses (q14): each defect found where it was planted."""

from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.core.data.provider import PriceBar
from quantlab.core.data.quality import CHECKS, quality_report, reference_sessions
from quantlab.core.universe import Instrument, Universe

_FIRST = date(2021, 1, 4)  # a Monday


def _bars(instrument_id: str, closes, first: date = _FIRST, step: int = 1) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=first + timedelta(days=step * i),
            open=float(close),
            high=float(close) * 1.01,
            low=float(close) * 0.99,
            close=float(close),
            volume=1e6,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def _walk(n: int = 120, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.01, n))


def _universe(periods_per_year: int) -> Universe:
    return Universe(
        name="u",
        asof_date=_FIRST,
        source="synthetic",
        periods_per_year=periods_per_year,
        instruments=[
            Instrument(id=i, symbol=i.upper(), asset_class="equity", quote_asset="USD")
            for i in ("aaa", "bbb")
        ],
    )


def _found(bars: dict[str, list[PriceBar]], sessions=None) -> dict[str, list]:
    sessions = (
        sessions if sessions is not None else sorted({b.ts for s in bars.values() for b in s})
    )
    report = quality_report(bars, sessions)
    return {
        check: [(f.instrument_id, f.day) for f in report.findings if f.check == check]
        for check in report.checks
    }


def test_clean_data_have_no_findings() -> None:
    bars = {"aaa": _bars("aaa", _walk()), "bbb": _bars("bbb", _walk(seed=4))}

    report = quality_report(bars, sorted({b.ts for s in bars.values() for b in s}))

    assert report.findings == []
    assert (report.instruments, report.bars) == (2, 240)
    assert report.summary() == {
        "instruments checked": 2.0,
        "bars checked": 240.0,
        **{check.name: 0.0 for check in CHECKS},
    }


def test_a_duplicate_date_and_a_zero_price_are_errors() -> None:
    series = _bars("aaa", _walk())
    series.insert(11, series[10])
    series[40] = replace(series[40], close=0.0, low=0.0)

    found = _found({"aaa": series})
    report = quality_report({"aaa": series}, [b.ts for b in series])

    assert found["duplicate dates"] == [("aaa", _FIRST + timedelta(days=10))]
    assert found["non-positive prices"] == [("aaa", series[40].ts)]
    assert {f.level for f in report.errors} == {"error"}
    assert len(report.errors) == 2


def test_a_delisting_bar_worth_nothing_is_not_an_error() -> None:
    series = _bars("aaa", _walk(30))
    series[-1] = replace(series[-1], open=0.0, high=0.0, low=0.0, close=0.0, delisting=True)

    assert quality_report({"aaa": series}, [b.ts for b in series]).errors == []


def test_a_high_below_the_close_is_inconsistent() -> None:
    series = _bars("aaa", _walk(30))
    series[7] = replace(series[7], high=series[7].close * 0.98)

    assert _found({"aaa": series})["inconsistent OHLC"] == [("aaa", series[7].ts)]


def test_a_session_other_instruments_traded_is_missing() -> None:
    full = _bars("aaa", _walk(50))
    holed = [bar for i, bar in enumerate(_bars("bbb", _walk(50, seed=4))) if i != 20]

    found = _found({"aaa": full, "bbb": holed})

    assert found["missing sessions"] == [("bbb", full[20].ts)]


def test_a_market_open_every_day_expects_every_calendar_day() -> None:
    both_skip = {
        name: [bar for i, bar in enumerate(_bars(name, _walk(40, seed=s))) if i != 15]
        for name, s in (("aaa", 3), ("bbb", 4))
    }

    crypto = reference_sessions(_universe(365), both_skip)
    weekdays = reference_sessions(_universe(252), both_skip)

    missing = _FIRST + timedelta(days=15)
    assert missing in crypto and missing not in weekdays
    assert _found(both_skip, crypto)["missing sessions"] == [("aaa", missing), ("bbb", missing)]
    assert _found(both_skip, weekdays)["missing sessions"] == []


def test_days_before_the_first_or_after_the_last_bar_are_not_missing() -> None:
    long = _bars("aaa", _walk(60))
    late = _bars("bbb", _walk(20, seed=4), first=_FIRST + timedelta(days=30))

    assert _found({"aaa": long, "bbb": late})["missing sessions"] == []


def test_five_equal_closes_in_a_row_are_stale() -> None:
    closes = _walk(60)
    closes[30:36] = closes[30]
    closes[45:49] = closes[45]  # four: not stale

    found = _found({"aaa": _bars("aaa", closes)})

    assert found["stale closes"] == [("aaa", _FIRST + timedelta(days=30))]


def test_a_split_left_unadjusted_is_an_extreme_move() -> None:
    closes = _walk(200)
    closes[120:] /= 4.0  # a 4:1 split nobody adjusted for

    found = _found({"aaa": _bars("aaa", closes)})

    assert found["extreme moves"] == [("aaa", _FIRST + timedelta(days=120))]


def test_too_short_or_constant_series_have_no_extreme_moves() -> None:
    short = _walk(15)
    short[10] *= 3.0
    flat = np.full(40, 100.0)

    found = _found({"aaa": _bars("aaa", short), "bbb": _bars("bbb", flat)})

    assert found["extreme moves"] == []


@pytest.mark.parametrize("check", CHECKS, ids=lambda c: c.name)
def test_every_check_only_reads(check) -> None:
    series = _bars("aaa", _walk(40))
    before = list(series)

    check.findings("aaa", series, [bar.ts for bar in series])

    assert series == before
