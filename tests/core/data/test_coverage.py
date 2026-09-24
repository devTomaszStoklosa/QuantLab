from datetime import date, timedelta

import pytest

from quantlab.core.data.coverage import price_coverage
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe

_FIRST = date(2024, 1, 1)


def _day(i: int) -> date:
    return _FIRST + timedelta(days=i)


def _bars(instrument_id: str, days: range) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=_day(i),
            open=10.0,
            high=10.0,
            low=10.0,
            close=10.0,
            volume=1.0,
            source="test",
        )
        for i in days
    ]


def _universe() -> Universe:
    ids = ("aaa", "bbb", "ccc", "idx")
    return Universe(
        name="pit",
        asof_date=_day(9),
        source="synthetic",
        periods_per_year=252,
        market_proxy="idx",
        instruments=[
            Instrument(id=i, symbol=i.upper(), asset_class="equity", quote_asset="USD") for i in ids
        ],
        memberships=[
            Membership(instrument_id="aaa", start=_day(0), end=None),
            Membership(instrument_id="bbb", start=_day(5), end=None),
            Membership(instrument_id="ccc", start=_day(0), end=_day(4)),
        ],
    )


def test_coverage_counts_member_days_with_a_price_and_names_members_without_any() -> None:
    bars = {
        "aaa": _bars("aaa", range(10)),
        "bbb": _bars("bbb", range(5, 8)),  # its prices stop 2 days early
        "idx": _bars("idx", range(10)),  # the benchmark is never a member
    }

    coverage = price_coverage(_universe(), bars, _day(0), _day(9))

    # aaa 10 of 10, bbb 3 of 5 (days 5-9), ccc 0 of 5 (days 0-4): the source lacks it.
    assert (coverage.priced_days, coverage.member_days) == (13, 20)
    assert coverage.share == pytest.approx(0.65)
    assert coverage.without_prices == ["ccc"]


def test_coverage_counts_only_the_window() -> None:
    bars = {"aaa": _bars("aaa", range(10)), "bbb": _bars("bbb", range(5, 10))}

    coverage = price_coverage(_universe(), bars, _day(5), _day(9))

    assert (coverage.priced_days, coverage.member_days) == (10, 10)
    assert coverage.without_prices == []
